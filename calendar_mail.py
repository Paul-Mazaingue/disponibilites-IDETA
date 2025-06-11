from exchangelib import Credentials, Account, Configuration, DELEGATE, EWSDateTime, EWSTimeZone
from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter
from cryptography.fernet import Fernet
from datetime import timedelta
import os
import json
import warnings
import urllib3
from dotenv import load_dotenv
load_dotenv()


# Supprimer les avertissements SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Désactiver vérification SSL au niveau du protocole
BaseProtocol.HTTP_ADAPTER_CLS = NoVerifyHTTPAdapter

# 🔐 Charger la clé secrète depuis les variables d’environnement
SECRET_KEY = os.environ.get("EXCHANGE_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("EXCHANGE_SECRET_KEY n’est pas définie dans les variables d’environnement")

fernet = Fernet(SECRET_KEY)

# 🔓 Lire et déchiffrer les identifiants
with open("credentials.enc", "rb") as f:
    decrypted = fernet.decrypt(f.read())
    creds = json.loads(decrypted.decode())

EMAIL = creds["email"]
MDP = creds["password"]

# Configuration Exchange locale
config = Configuration(
    server="sidetavm20.ideta.dom",
    credentials=Credentials(EMAIL, MDP)
)

# Création de l'objet compte
account = Account(
    primary_smtp_address=EMAIL,
    config=config,
    autodiscover=False,
    access_type=DELEGATE
)

# Fuseau horaire et période à analyser
tz = EWSTimeZone('Europe/Paris')
# start from 2-06-2025 to 19-06-2025
from datetime import datetime, timedelta

start = EWSDateTime(2025, 6, 2, tzinfo=tz)
end = EWSDateTime(2025, 6, 19, tzinfo=tz)
#start = EWSDateTime.now(tz)
#end = start + timedelta(days=7)

# Liste des événements
for item in account.calendar.view(start=start, end=end).order_by('start'):
    print(f"{item.start} - {item.end} : {item.subject}")
