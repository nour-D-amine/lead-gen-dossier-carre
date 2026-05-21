import os
import logging
import threading
import subprocess
import sys
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import config

app = Flask(__name__, static_folder='dashboard')
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

# Pipeline execution state
pipeline_running = False
pipeline_status = "Inactif"
pipeline_error = None

def get_python_executable():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(base_dir, '.venv', 'bin', 'python')
    if os.path.exists(venv_python):
        return venv_python
    venv_python3 = os.path.join(base_dir, '.venv', 'bin', 'python3')
    if os.path.exists(venv_python3):
        return venv_python3
    return sys.executable

def run_pipeline_task():
    global pipeline_running, pipeline_status, pipeline_error
    pipeline_running = True
    pipeline_status = "Initialisation du script..."
    pipeline_error = None
    
    try:
        python_exe = get_python_executable()
        main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
        
        logger.info(f"Lancement de la commande : {python_exe} {main_script} --batch-size 5 --max-leads 5")
        pipeline_status = "Démarrage du pipeline d'enrichissement..."
        
        process = subprocess.Popen(
            [python_exe, main_script, "--batch-size", "5", "--max-leads", "5"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # Read the stdout in real-time
        for line in process.stdout:
            clean_line = line.strip()
            if clean_line:
                logger.info(f"[Pipeline] {clean_line}")
                # Parse key milestones for user-friendly UI feedback
                if "COUCHE 1" in clean_line:
                    pipeline_status = "Phase 1 : Extraction des leads (Annuaire Entreprises)..."
                elif "COUCHE 2" in clean_line:
                    pipeline_status = "Phase 2 : Enrichissement des leads (BOAMP & Sites Web)..."
                elif "COUCHE 3" in clean_line:
                    pipeline_status = "Phase 3 : Analyse IA (Frictions & Drafts)..."
                elif "Enregistrement de" in clean_line:
                    pipeline_status = "Enregistrement des leads dans le fichier CSV..."
                elif "push_to_google_sheets" in clean_line or "Pushing" in clean_line:
                    pipeline_status = "Synchronisation en cours avec Google Sheets..."
                elif "nouveaux leads" in clean_line:
                    pipeline_status = clean_line
        
        process.wait()
        if process.returncode == 0:
            pipeline_status = "Succès ! Leads enrichis et synchronisés avec succès."
        else:
            pipeline_error = f"Le script s'est arrêté avec le code d'erreur {process.returncode}."
            pipeline_status = "Erreur d'exécution."
    except Exception as e:
        logger.error(f"Erreur d'exécution de la pipeline : {e}")
        pipeline_error = str(e)
        pipeline_status = "Erreur lors du lancement du processus."
    finally:
        pipeline_running = False

def get_google_sheets_data():
    try:
        if not os.path.exists(config.GOOGLE_CREDENTIALS_PATH):
            return {"error": "Fichier credentials.json introuvable."}
            
        creds = Credentials.from_service_account_file(config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
        client = gspread.authorize(creds)
        spreadsheet = client.open(config.GOOGLE_SHEET_NAME)
        worksheet = spreadsheet.sheet1
        
        # Récupérer toutes les valeurs
        records = worksheet.get_all_records()
        return {"data": records}
    except Exception as e:
        logger.error(f"Erreur API Google Sheets: {e}")
        return {"error": str(e)}

@app.route('/api/leads', methods=['GET'])
def api_leads():
    data = get_google_sheets_data()
    if "error" in data:
        return jsonify(data), 500
    return jsonify(data)

@app.route('/api/pipeline/run', methods=['POST'])
def run_pipeline_api():
    global pipeline_running
    if pipeline_running:
        return jsonify({"error": "Le pipeline d'enrichissement est déjà en cours d'exécution."}), 400
        
    thread = threading.Thread(target=run_pipeline_task)
    thread.daemon = True
    thread.start()
    return jsonify({"message": "Pipeline démarré avec succès en arrière-plan."})

@app.route('/api/pipeline/status', methods=['GET'])
def pipeline_status_api():
    global pipeline_running, pipeline_status, pipeline_error
    return jsonify({
        "running": pipeline_running,
        "status": pipeline_status,
        "error": pipeline_error
    })

@app.route('/')
def serve_index():
    return send_from_directory('dashboard', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('dashboard', path)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Démarrage du serveur Dashboard sur le port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
