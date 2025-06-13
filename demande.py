import os
import json
import tempfile
from datetime import datetime, timedelta
import pytz
import time
from rclone import rclone_lsjson, rclone_copy, rclone_upload, rclone_delete
from getCalendar import get_specific_period_events
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

RCLONE_REMOTE = os.getenv("RCLONE_REMOTE")
FOLDER_DEMANDES = os.getenv("FOLDER_DEMANDES")
FOLDER_REPONSES = os.getenv("FOLDER_REPONSES")
TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "Europe/Paris"))

tmp_dir = tempfile.mkdtemp()

def normaliser_heure(valeur, par_defaut="09:00"):
    print(f"Normalisation de l'heure : {valeur}, par défaut : {par_defaut}")
    if not valeur:
        return par_defaut
    parties = valeur.strip().split(":")
    if len(parties) == 1:
        heures = int(parties[0])
        minutes = 0
    else:
        heures = int(parties[0])
        minutes = int(parties[1])
    return f"{heures:02d}:{minutes:02d}"

def trouver_disponibilites(events, debut, fin, heure_debut, heure_fin, duree):
    dispo = []
    jour = debut

    while jour <= fin:
        h_debut = TIMEZONE.localize(datetime.combine(jour, heure_debut))
        h_fin = TIMEZONE.localize(datetime.combine(jour, heure_fin))

        evts_jour = []
        for e in events:
            # Ignorer les événements toute la journée (all day)
            if getattr(e, "is_all_day", False):
                continue

            # Gérer proprement EWSDate vs EWSDateTime
            try:
                e_debut = e.start.datetime if hasattr(e.start, "datetime") else e.start
                e_fin = e.end.datetime if hasattr(e.end, "datetime") else e.end
            except AttributeError:
                continue  # on saute l'événement s'il est mal formé

            if isinstance(e_debut, datetime):
                if e_debut.tzinfo is None:
                    e_debut = TIMEZONE.localize(e_debut)
                else:
                    e_debut = e_debut.astimezone(TIMEZONE)
            else:
                # Cas rare d'EWSDate (on ignore)
                continue

            if isinstance(e_fin, datetime):
                if e_fin.tzinfo is None:
                    e_fin = TIMEZONE.localize(e_fin)
                else:
                    e_fin = e_fin.astimezone(TIMEZONE)
            else:
                continue

            if e_debut.date() == jour:
                nom = e.subject if hasattr(e, "subject") else "Sans titre"
                evts_jour.append((e_debut, e_fin, nom))

        evts_jour.sort(key=lambda x: x[0])

        curseur = h_debut
        for e_debut, e_fin, nom in evts_jour:
            print("Événement:", nom)
            print(" - Début :", e_debut)
            print(" - Fin   :", e_fin)

            if (e_debut - curseur) >= duree:
                dispo.append((curseur, e_debut))

            curseur = max(curseur, e_fin)

        if (h_fin - curseur) >= duree:
            dispo.append((curseur, h_fin))

        jour += timedelta(days=1)

    return dispo


def traiter_fichier(demande_nom):
    # id of the request
    id_req = demande_nom.replace("demande_", "").replace(".json", "")

    # Saving the request in a temporary directory
    chemin_demande = os.path.join(tmp_dir, demande_nom)
    rclone_copy(f"{FOLDER_DEMANDES}/{demande_nom}", chemin_demande)

    # Reading the request data
    with open(chemin_demande, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(data)

    # Parsing the request data
    debut = datetime.strptime(data["date"], "%Y-%m-%d").date()
    fin = datetime.strptime(data["date_1"], "%Y-%m-%d").date()
    duree = timedelta(hours=float(data["duree"]))
    h_debut = datetime.strptime(normaliser_heure(data.get("heureDebutTravail", "09:00"), "09:00"), "%H:%M").time()
    h_fin = datetime.strptime(normaliser_heure(data.get("heureFinTravail", "18:00"), "18:00"), "%H:%M").time()

    # Get events from the calendar for the specified period
    events = get_specific_period_events(
        start_year=debut.year, start_month=debut.month, start_day=debut.day,
        end_year=fin.year, end_month=fin.month, end_day=fin.day
    )

    # Find available time slots
    dispo = trouver_disponibilites(events, debut, fin, h_debut, h_fin, duree)

    # Message to be sent
    lignes = [
        f"Information recherche : Début : {data['date']} Fin : {data['date_1']} Durée : {data['duree']} h",
        f"Horaire de travail : {h_debut.strftime('%H:%M')} - {h_fin.strftime('%H:%M')}",
        "Voici mes disponibilités :"
    ]
    for d1, d2 in dispo:
        lignes.append(f"{d1.strftime('%d/%m/%Y à %H:%M')} à {d2.strftime('%H:%M')}")

    reponse_nom = f"reponse_{id_req}.txt"

    chemin_rep = os.path.join(tmp_dir, reponse_nom)
    with open(chemin_rep, "w", encoding="utf-8") as f:
        f.write("<br>".join(lignes))

    rclone_upload(chemin_rep, f"{FOLDER_REPONSES}/{reponse_nom}")
    rclone_delete(f"{FOLDER_DEMANDES}/{demande_nom}")
    
    print(f"✅ Réponse générée pour : {id_req}")

if __name__ == "__main__":
    while True:
        demandes = rclone_lsjson(FOLDER_DEMANDES)
        for f in demandes:
            if f["Name"].startswith("demande_") and f["Name"].endswith(".json"):
                traiter_fichier(f["Name"])
        time.sleep(2)
