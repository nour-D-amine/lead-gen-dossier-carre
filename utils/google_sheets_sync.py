import logging
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import os

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def push_to_google_sheets(
    credentials_path: str,
    sheet_name: str,
    csv_path: str
) -> bool:
    """
    Lit le fichier CSV final et écrase/remplace le contenu du Google Sheet ciblé.
    Cela permet au Dashboard Looker/AI Studio d'être toujours à jour.
    """
    if not os.path.exists(credentials_path):
        logger.error(f"Google Sheets : Fichier de credentials introuvable ({credentials_path})")
        return False

    if not os.path.exists(csv_path):
        logger.error(f"Google Sheets : Fichier CSV introuvable ({csv_path})")
        return False

    try:
        # 1. Charger les credentials
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        client = gspread.authorize(creds)

        # 2. Ouvrir le sheet
        try:
            spreadsheet = client.open(sheet_name)
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"Google Sheets : Le fichier '{sheet_name}' n'a pas été trouvé. Assurez-vous de l'avoir partagé avec l'email du Service Account.")
            return False
            
        worksheet = spreadsheet.sheet1

        # 3. Lire le CSV avec pandas (remplacer les NaN par des chaînes vides)
        df = pd.read_csv(csv_path).fillna("")

        # 4. Préparer les données pour gspread
        data_to_upload = [df.columns.values.tolist()] + df.values.tolist()

        # 5. Mettre à jour en un seul batch
        worksheet.clear()
        worksheet.update(values=data_to_upload, range_name=None)
        
        logger.info(f"Google Sheets : {len(df)} leads synchronisés avec succès sur '{sheet_name}'.")
        return True

    except Exception as e:
        logger.error(f"Erreur lors de la synchronisation Google Sheets : {e}")
        return False
