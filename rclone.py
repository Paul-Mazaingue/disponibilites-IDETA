
import os
import json
import subprocess
import tempfile
from datetime import datetime, timedelta
from ics import Calendar
import pytz
import time

RCLONE_REMOTE = "dispo"
FOLDER_DEMANDES = "Partage/Demandes"
FOLDER_REPONSES = "Partage/Réponses"

def rclone_lsjson(path):
    """List files in a remote directory using rclone and return as JSON."""
    result = subprocess.run(["rclone", "lsjson", f"{RCLONE_REMOTE}:{path}"], capture_output=True, text=True)
    return json.loads(result.stdout)

def rclone_copy(remote_path, local_path):
    subprocess.run(["rclone", "copyto", f"{RCLONE_REMOTE}:{remote_path}", local_path], check=True)

def rclone_upload(local_path, remote_path):
    subprocess.run(["rclone", "copyto", local_path, f"{RCLONE_REMOTE}:{remote_path}"], check=True)

def rclone_delete(remote_path):
    subprocess.run(["rclone", "delete", f"{RCLONE_REMOTE}:{remote_path}"], check=True)