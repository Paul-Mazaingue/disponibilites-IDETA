# generate_key.py
from cryptography.fernet import Fernet

key = Fernet.generate_key()
with open("secret.key", "wb") as key_file:
    key_file.write(key)
print("Clé générée et enregistrée dans secret.key")
