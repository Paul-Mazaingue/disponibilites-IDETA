import os
import json
import subprocess
import tempfile
from datetime import datetime, timedelta
from ics import Calendar
import pytz
import time

# Config
RCLONE_REMOTE = "dispo"
FOLDER_CALENDRIERS = "Partage/Calendriers"
FOLDER_DEMANDES = "Partage/Demandes"
FOLDER_REPONSES = "Partage/Réponses"
TIMEZONE = pytz.timezone("Europe/Paris")

tmp_dir = tempfile.mkdtemp()

def normaliser_heure(valeur, par_defaut="09:00"):
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


def rclone_lsjson(path):
    result = subprocess.run(["rclone", "lsjson", f"{RCLONE_REMOTE}:{path}"], capture_output=True, text=True)
    return json.loads(result.stdout)

def rclone_copy(remote_path, local_path):
    subprocess.run(["rclone", "copyto", f"{RCLONE_REMOTE}:{remote_path}", local_path], check=True)

def rclone_upload(local_path, remote_path):
    subprocess.run(["rclone", "copyto", local_path, f"{RCLONE_REMOTE}:{remote_path}"], check=True)

def rclone_delete(remote_path):
    subprocess.run(["rclone", "delete", f"{RCLONE_REMOTE}:{remote_path}"], check=True)

def lire_ics(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        contenu = f.read()
        calendriers = Calendar.parse_multiple(contenu)
        evenements = []
        for cal in calendriers:
            evenements.extend(cal.events)
        return sorted(evenements, key=lambda e: e.begin)


def trouver_disponibilites(events, debut, fin, heure_debut, heure_fin, duree):
    dispo = []
    jour = debut
    while jour <= fin:
        h_debut = TIMEZONE.localize(datetime.combine(jour, heure_debut))
        h_fin = TIMEZONE.localize(datetime.combine(jour, heure_fin))
        evts_jour = [e for e in events if e.begin.date() == jour]
        curseur = h_debut
        for evt in evts_jour:
            e_debut = evt.begin.astimezone(TIMEZONE)
            if e_debut > curseur + duree:
                dispo.append((curseur, e_debut))
            curseur = max(curseur, evt.end.astimezone(TIMEZONE))
        if curseur + duree <= h_fin:
            dispo.append((curseur, h_fin))
        jour += timedelta(days=1)
    return dispo

def traiter_fichier(demande_nom):
    id_req = demande_nom.replace("demande_", "").replace(".json", "")
    chemin_demande = os.path.join(tmp_dir, demande_nom)
    rclone_copy(f"{FOLDER_DEMANDES}/{demande_nom}", chemin_demande)

    with open(chemin_demande, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(data)
    debut = datetime.strptime(data["date"], "%Y-%m-%d").date()
    fin = datetime.strptime(data["date_1"], "%Y-%m-%d").date()
    duree = timedelta(hours=float(data["duree"]))
    h_debut = datetime.strptime(normaliser_heure(data.get("heureDebutTravail", "09:00")), "%H:%M").time()
    h_fin = datetime.strptime(normaliser_heure(data.get("heureFinTravail", "18:00")), "%H:%M").time()


    nom_cal = f"calendrier_{id_req}.ics"
    chemin_cal = os.path.join(tmp_dir, nom_cal)
    rclone_copy(f"{FOLDER_CALENDRIERS}/{nom_cal}", chemin_cal)
    events = lire_ics(chemin_cal)
    dispo = trouver_disponibilites(events, debut, fin, h_debut, h_fin, duree)

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
        f.write("\n".join(lignes))

    rclone_upload(chemin_rep, f"{FOLDER_REPONSES}/{reponse_nom}")
    rclone_delete(f"{FOLDER_DEMANDES}/{demande_nom}")
    rclone_delete(f"{FOLDER_CALENDRIERS}/{nom_cal}")
    print(f"✅ Réponse générée pour : {id_req}")

# ----- Script principal (boucle continue, vérifie toutes les 5 secondes) -----
while True:
    demandes = rclone_lsjson(FOLDER_DEMANDES)
    for f in demandes:
        if f["Name"].startswith("demande_") and f["Name"].endswith(".json"):
            traiter_fichier(f["Name"])
    time.sleep(5)
