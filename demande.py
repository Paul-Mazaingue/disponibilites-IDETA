import os
import json
import tempfile
import pytz
import time
from rclone import rclone_lsjson, rclone_copy, rclone_upload, rclone_delete
from getCalendar import get_specific_period_events
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pytz import timezone
from exchangelib.ewsdatetime import EWSDateTime, EWSDate
# Charger les variables d'environnement
load_dotenv()

RCLONE_REMOTE = os.getenv("RCLONE_REMOTE")
FOLDER_DEMANDES = os.getenv("FOLDER_DEMANDES")
FOLDER_REPONSES = os.getenv("FOLDER_REPONSES")
TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "Europe/Paris"))

tmp_dir = tempfile.mkdtemp()
UTC = pytz.utc

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

def trouver_disponibilites(events,
                           debut,
                           fin,
                           heure_debut,
                           heure_fin,
                           duree,
                           weekend,
                           excludedDates):
    """
    events: liste d'événements Exchange
    debut, fin: dates (date objects)
    heure_debut, heure_fin: hours (time objects)
    duree: timedelta
    weekend: bool – si False, on saute samedis et dimanches
    excludedDates: liste de date objects à exclure
    """
    busy = []
    # 1) normalisation des events en datetime Europe/Paris
    for ev in events:
        s0, e0 = ev.start, ev.end

        # a) EWSDate (date-only) → bloquer toute la journée
        if isinstance(s0, EWSDate) and not isinstance(s0, EWSDateTime):
            s_py = datetime(s0.year, s0.month, s0.day, 0, 0)
            e_py = datetime(e0.year, e0.month, e0.day, 0, 0) + timedelta(days=1)

        # b) EWSDateTime → Python datetime via ISO
        elif isinstance(s0, EWSDateTime):
            s_py = datetime.fromisoformat(s0.isoformat())
            e_py = datetime.fromisoformat(e0.isoformat())

        # c) sinon c’est déjà un datetime Python
        else:
            s_py, e_py = s0, e0

        # 2) localiser ou convertir en Europe/Paris
        if s_py.tzinfo is None:
            s_loc = TIMEZONE.localize(s_py)
            e_loc = TIMEZONE.localize(e_py)
        else:
            s_loc = s_py.astimezone(TIMEZONE)
            e_loc = e_py.astimezone(TIMEZONE)

        busy.append((s_loc, e_loc))

    # 3) trier par heure de début
    busy.sort(key=lambda x: x[0])

    disponibilites = []
    jour = debut
    while jour <= fin:
        # 4a) exclure les dates marquées
        if jour in excludedDates:
            jour += timedelta(days=1)
            continue

        # 4b) exclure le weekend si demandé
        if not weekend and jour.weekday() >= 5:
            jour += timedelta(days=1)
            continue

        # 5) fenêtre de travail pour ce jour
        base_debut = TIMEZONE.localize(datetime.combine(jour, heure_debut))
        base_fin   = TIMEZONE.localize(datetime.combine(jour, heure_fin))

        # 6) intersection des events avec la fenêtre
        today = [
            (max(s, base_debut), min(e, base_fin))
            for s, e in busy
            if e > base_debut and s < base_fin
        ]

        # 7) fusion des créneaux occupés
        merged = []
        for s2, e2 in sorted(today, key=lambda x: x[0]):
            if not merged or s2 > merged[-1][1]:
                merged.append([s2, e2])
            else:
                merged[-1][1] = max(merged[-1][1], e2)

        # 8) chercher les créneaux libres, clamp + filtre durée
        def add_slot(start, end):
            sc = max(start, base_debut)
            ec = min(end,   base_fin)
            if (ec - sc) >= duree:
                disponibilites.append((sc, ec))

        if not merged:
            add_slot(base_debut, base_fin)
        else:
            add_slot(base_debut,         merged[0][0])
            for i in range(len(merged) - 1):
                add_slot(merged[i][1], merged[i + 1][0])
            add_slot(merged[-1][1],     base_fin)

        jour += timedelta(days=1)

    return disponibilites


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
    weekend = data.get("weekend", "false").lower() == "true"
    # Parse excludedDates from the request (format: '11-05-2025,12-05-2025')
    excludedDates = [
        datetime.strptime(date_str.strip(), "%d-%m-%Y").date()
        for date_str in data.get("excludedDates", "").split(",")
        if date_str.strip()
    ]

    # Get events from the calendar for the specified period
    events = get_specific_period_events(
        start_year=debut.year, start_month=debut.month, start_day=debut.day,
        end_year=fin.year, end_month=fin.month, end_day=fin.day
    )

    # Message to be sent
    lignes = [
        f"Information recherche : Début : {data['date']} Fin : {data['date_1']} Durée : {data['duree']} h",
        f"Horaire de travail : {h_debut.strftime('%H:%M')} - {h_fin.strftime('%H:%M')}",
        "Voici mes disponibilités :"
    ]

    try:
        # Find available time slots
        dispo = trouver_disponibilites(events, debut, fin, h_debut, h_fin, duree, weekend, excludedDates)    

        for d1, d2 in dispo:
            lignes.append(f"{d1.strftime('%d/%m/%Y à %H:%M')} à {d2.strftime('%H:%M')}")
    except Exception as e:
        lignes.append(f"Erreur lors de la récupération des disponibilités : {str(e)}")
        print(f"❌ Erreur pour {id_req} : {str(e)}")

    reponse_nom = f"reponse_{id_req}.txt"

    chemin_rep = os.path.join(tmp_dir, reponse_nom)
    with open(chemin_rep, "w", encoding="utf-8") as f:
        f.write("<br>".join(lignes))

    rclone_upload(chemin_rep, f"{FOLDER_REPONSES}/{reponse_nom}")
    rclone_delete(f"{FOLDER_DEMANDES}/{demande_nom}")
    
    print(f"✅ Réponse générée pour : {id_req}")

if __name__ == "__main__":

    demandes = rclone_lsjson(FOLDER_DEMANDES)
    for f in demandes:
        if f["Name"].startswith("demande_") and f["Name"].endswith(".json"):
            traiter_fichier(f["Name"])

    """
    while True:
        demandes = rclone_lsjson(FOLDER_DEMANDES)
        for f in demandes:
            if f["Name"].startswith("demande_") and f["Name"].endswith(".json"):
                traiter_fichier(f["Name"])
        time.sleep(1000)
    """
