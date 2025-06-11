# encrypt_credentials.py
from cryptography.fernet import Fernet
import json
import getpass

# Charger la clé générée
with open("secret.key", "rb") as key_file:
    key = key_file.read()

fernet = Fernet(key)

email = input("Adresse email : ")
password = getpass.getpass("Mot de passe : ")

credentials = json.dumps({"email": email, "password": password}).encode()
encrypted = fernet.encrypt(credentials)

with open("credentials.enc", "wb") as enc_file:
    enc_file.write(encrypted)

print("Identifiants chiffrés avec succès.")
