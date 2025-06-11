from cryptography.fernet import Fernet
import json

# Lire la clé
with open("secret.key", "rb") as key_file:
    key = key_file.read()
fernet = Fernet(key)

# Lire et déchiffrer les identifiants
with open("credentials.enc", "rb") as enc_file:
    encrypted_data = enc_file.read()
decrypted_data = fernet.decrypt(encrypted_data)

credentials = json.loads(decrypted_data)
email = credentials["email"]
password = credentials["password"]