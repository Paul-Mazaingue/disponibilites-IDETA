##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
## 
## Faire en sorte qu'on puise mettre des nombre à virgule pour la durée
## Supprimer le fichier réponse une fois la demande traitée sur power automate
##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
##
import time
from rclone import rclone_lsjson
from demande import traiter_fichier


RCLONE_REMOTE = "dispo"
FOLDER_DEMANDES = "Partage/Demandes"
FOLDER_REPONSES = "Partage/Réponses"

if __name__ == "__main__":
    while True:
        demandes = rclone_lsjson(FOLDER_DEMANDES)
        for f in demandes:
            if f["Name"].startswith("demande_") and f["Name"].endswith(".json"):
                traiter_fichier(f["Name"])
        time.sleep(2)