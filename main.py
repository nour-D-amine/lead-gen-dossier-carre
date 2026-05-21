"""
main.py — Orchestrateur 3 couches Lead Gen BTP
Pipeline : Ingestion → Enrichissement → Intelligence → CSV

Usage:
    python3 main.py                          # Exécution complète
    python3 main.py --dry-run                # Test sans consommer d'API payantes
    python3 main.py --batch-size 10          # Batch de 10 leads
    python3 main.py --max-leads 50           # Limiter à 50 leads
    python3 main.py --naf 43.21A --region 11 # Un seul code NAF × région
"""

import argparse
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import httpx
from google import genai

import config
from utils.rate_limiter import RateLimiter
from utils.api_annuaire import fetch_all_for_naf_region, parse_entreprise
from utils.api_boamp import fetch_activite_boamp
from utils.api_firecrawl import scrape_website_markdown
from utils.api_gemini import analyze_batch
from utils.web_search import find_company_website
from utils.google_sheets_sync import push_to_google_sheets

# ── Logging ──────────────────────────────────────────────────────
def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Console handler (INFO)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(config.LOG_FORMAT, config.LOG_DATE_FORMAT))
    root_logger.addHandler(ch)

    # File handler (DEBUG)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(config.LOG_FORMAT, config.LOG_DATE_FORMAT))
    root_logger.addHandler(fh)

    return logging.getLogger("main")


# ── Checkpoint ───────────────────────────────────────────────────
def load_checkpoint(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_sirens": [], "last_naf": None, "last_region": None, "phase": "ingestion"}


def save_checkpoint(path: Path, checkpoint: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


# ── CSV ──────────────────────────────────────────────────────────
def load_existing_sirens(csv_path: Path) -> set[str]:
    if not csv_path.exists():
        return set()
    sirens = set()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sirens.add(row.get("SIREN", ""))
    return sirens


def init_csv(csv_path: Path) -> None:
    if not csv_path.exists():
        csv_path.parent.mkdir(exist_ok=True)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=config.CSV_COLUMNS)
            writer.writeheader()


def append_leads_to_csv(csv_path: Path, leads: list[dict]) -> None:
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=config.CSV_COLUMNS)
        for lead in leads:
            writer.writerow({
                "SIREN": lead.get("siren", ""),
                "Nom": lead.get("nom", ""),
                "NAF": lead.get("naf", ""),
                "Dirigeant": lead.get("dirigeant", ""),
                "Email": lead.get("email", ""),
                "Site Web": lead.get("site_web", ""),
                "Activité BOAMP": lead.get("activite_boamp", ""),
                "Analyse Friction": lead.get("analyse_friction", ""),
                "Draft Email": lead.get("draft_email", ""),
                "Statut Traitement": lead.get("statut_traitement", "À optimiser"),
            })


# ── Pipeline ─────────────────────────────────────────────────────
def run_pipeline(args: argparse.Namespace) -> None:
    logger = setup_logging(config.LOGS_DIR)
    logger.info("=" * 60)
    logger.info("Lead Gen BTP — Dossier Carré — Démarrage")
    logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Max leads: {args.max_leads or 'Illimité'}")
    logger.info("=" * 60)

    # Init rate limiters
    rl_annuaire = RateLimiter("Annuaire", **config.RATE_LIMITS["annuaire"])
    rl_boamp = RateLimiter("BOAMP", **config.RATE_LIMITS["boamp"])
    rl_firecrawl = RateLimiter("Firecrawl", **config.RATE_LIMITS["firecrawl"])
    rl_gemini = RateLimiter("Gemini", **config.RATE_LIMITS["gemini"])

    # Init checkpoint & CSV
    checkpoint = load_checkpoint(config.CHECKPOINT_PATH)
    existing_sirens = load_existing_sirens(config.CSV_PATH)
    init_csv(config.CSV_PATH)

    logger.info(f"Checkpoint: {len(checkpoint.get('processed_sirens', []))} SIREN déjà traités")
    logger.info(f"CSV existant: {len(existing_sirens)} SIREN")

    processed_sirens = set(checkpoint.get("processed_sirens", []))
    all_sirens = existing_sirens | processed_sirens

    # Déterminer les codes NAF et régions à traiter
    naf_codes = [args.naf] if args.naf else config.NAF_CODES
    regions = [args.region] if args.region else config.REGIONS

    # ── COUCHE 1 : Data Ingestion ──────────────────────────────
    logger.info("━━━ COUCHE 1 : Data Ingestion (Annuaire Entreprises) ━━━")

    all_leads = []
    total_fetched = 0

    with httpx.Client() as http_client:
        for naf_code in naf_codes:
            for region in regions:
                # Skip si déjà traité (checkpoint)
                checkpoint_key = f"{naf_code}_{region}"
                if checkpoint.get("completed_combos") and checkpoint_key in checkpoint["completed_combos"]:
                    logger.debug(f"Skip {checkpoint_key} (déjà traité)")
                    continue

                leads = fetch_all_for_naf_region(
                    http_client, rl_annuaire, naf_code, region,
                    max_pages=args.max_pages,
                    categories_exclues=config.CATEGORIES_EXCLUES,
                )

                # Dédoublonner
                new_leads = []
                for lead in leads:
                    siren = lead["siren"]
                    if siren not in all_sirens:
                        all_sirens.add(siren)
                        new_leads.append(lead)

                all_leads.extend(new_leads)
                total_fetched += len(new_leads)

                # Mettre à jour le checkpoint
                if "completed_combos" not in checkpoint:
                    checkpoint["completed_combos"] = []
                checkpoint["completed_combos"].append(checkpoint_key)
                save_checkpoint(config.CHECKPOINT_PATH, checkpoint)

                logger.info(
                    f"NAF {naf_code} × Région {region}: "
                    f"+{len(new_leads)} nouveaux leads (total: {total_fetched})"
                )

                # Vérifier la limite
                if args.max_leads and total_fetched >= args.max_leads:
                    all_leads = all_leads[:args.max_leads]
                    logger.info(f"Limite atteinte: {args.max_leads} leads")
                    break
            if args.max_leads and total_fetched >= args.max_leads:
                break

    logger.info(f"Couche 1 terminée: {len(all_leads)} leads à enrichir")

    if not all_leads:
        logger.warning("Aucun lead à traiter. Fin.")
        return

    # ── COUCHE 2 : Enrichissement ──────────────────────────────
    logger.info("━━━ COUCHE 2 : Enrichissement (BOAMP + Firecrawl) ━━━")

    if not args.dry_run and config.GEMINI_API_KEY:
        llm_client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Traitement par batch
    for batch_start in range(0, len(all_leads), args.batch_size):
        batch = all_leads[batch_start:batch_start + args.batch_size]
        batch_num = (batch_start // args.batch_size) + 1
        total_batches = (len(all_leads) + args.batch_size - 1) // args.batch_size

        logger.info(f"── Batch {batch_num}/{total_batches} ({len(batch)} leads) ──")

        # Définition de la fonction d'enrichissement d'un lead (fermeture)
        def enrich_single_lead(lead_item: dict, client_http: httpx.Client) -> None:
            siren_val = lead_item["siren"]
            nom_val = lead_item["nom"]

            if siren_val in processed_sirens:
                return

            # BOAMP : recherche activité marchés publics
            try:
                lead_item["activite_boamp"] = fetch_activite_boamp(
                    client_http, rl_boamp, nom_val,
                    months_lookback=config.BOAMP_MONTHS_LOOKBACK,
                )
            except Exception as exc:
                logger.warning(f"BOAMP échoué pour {nom_val}: {exc}")
                lead_item["activite_boamp"] = "Aucune activité détectée"

            # Recherche du site web
            lead_item["site_web"] = find_company_website(nom_val)
            lead_item["site_markdown"] = ""

            if not args.dry_run and config.FIRECRAWL_API_KEY and lead_item.get("site_web"):
                try:
                    lead_item["site_markdown"] = scrape_website_markdown(
                        client_http, rl_firecrawl,
                        config.FIRECRAWL_API_KEY, lead_item["site_web"],
                    )
                except Exception as exc:
                    logger.warning(f"Firecrawl échoué pour {nom_val}: {exc}")

        with httpx.Client() as http_client:
            from concurrent.futures import ThreadPoolExecutor
            logger.info(f"Enrichissement parallèle de {len(batch)} leads...")
            with ThreadPoolExecutor(max_workers=min(len(batch), 10)) as executor:
                futures = [executor.submit(enrich_single_lead, lead, http_client) for lead in batch]
                for future in futures:
                    try:
                        future.result()
                    except Exception as pool_err:
                        logger.error(f"Erreur d'enrichissement parallèle dans le pool : {pool_err}")

        # ── COUCHE 3 : Intelligence (Gemini 2.5 Pro) ──────────────────
        if not args.dry_run and llm_client:
            logger.info(f"── Couche 3 : Gemini Pro analyse batch {batch_num} ──")

            # Batch LLM par lots de GEMINI_BATCH_SIZE
            for cb_start in range(0, len(batch), config.GEMINI_BATCH_SIZE):
                cb = batch[cb_start:cb_start + config.GEMINI_BATCH_SIZE]
                results = analyze_batch(llm_client, rl_gemini, cb)

                for lead, (analyse, email_draft, contact_email) in zip(cb, results):
                    lead["analyse_friction"] = analyse
                    lead["draft_email"] = email_draft
                    lead["email"] = contact_email
                    lead["statut_traitement"] = "À optimiser"
        else:
            for lead in batch:
                lead["analyse_friction"] = "[DRY-RUN] Analyse non générée"
                lead["draft_email"] = "[DRY-RUN] Email non généré"
                lead["email"] = ""
                lead["statut_traitement"] = "À optimiser"

        # ── Export CSV ────────────────────────────────────────
        append_leads_to_csv(config.CSV_PATH, batch)

        # Mise à jour checkpoint
        for lead in batch:
            processed_sirens.add(lead["siren"])
        checkpoint["processed_sirens"] = list(processed_sirens)
        save_checkpoint(config.CHECKPOINT_PATH, checkpoint)

        logger.info(
            f"Batch {batch_num} terminé — "
            f"{len(processed_sirens)} leads traités au total"
        )

    # ── COUCHE 4 : Synchronisation Google Sheets ─────────────────
    logger.info("━━━ COUCHE 4 : Synchronisation Google Sheets ━━━")
    if not args.dry_run:
        success = push_to_google_sheets(
            config.GOOGLE_CREDENTIALS_PATH,
            config.GOOGLE_SHEET_NAME,
            config.CSV_PATH
        )
        if success:
            logger.info("Synchronisation Google Sheets réussie.")
        else:
            logger.error("Échec de la synchronisation Google Sheets.")
    else:
        logger.info("[DRY-RUN] Synchronisation ignorée.")

    # ── Résumé final ─────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Pipeline terminé !")
    logger.info(f"Total leads traités: {len(processed_sirens)}")
    logger.info(f"CSV: {config.CSV_PATH}")
    logger.info(f"Rate limiters finaux:")
    logger.info(f"  {rl_annuaire}")
    logger.info(f"  {rl_boamp}")
    logger.info(f"  {rl_firecrawl}")
    logger.info(f"  {rl_gemini}")
    logger.info("=" * 60)


# ── CLI ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Lead Gen BTP — Pipeline B.L.A.S.T",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Exécuter sans appeler les APIs payantes (Firecrawl, Gemini)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=config.DEFAULT_BATCH_SIZE,
        help=f"Taille des batchs de traitement (défaut: {config.DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--max-leads", type=int, default=None,
        help="Nombre maximum de leads à traiter",
    )
    parser.add_argument(
        "--max-pages", type=int, default=None,
        help="Nombre max de pages par combo NAF×Région (pour tests)",
    )
    parser.add_argument(
        "--naf", type=str, default=None,
        help="Code NAF spécifique à traiter (ex: 43.21A)",
    )
    parser.add_argument(
        "--region", type=str, default=None,
        help="Code région spécifique (ex: 11 pour IDF)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Réinitialiser le checkpoint et le CSV",
    )

    args = parser.parse_args()

    # Reset si demandé
    if args.reset:
        if config.CHECKPOINT_PATH.exists():
            config.CHECKPOINT_PATH.unlink()
        if config.CSV_PATH.exists():
            config.CSV_PATH.unlink()
        print("Checkpoint et CSV réinitialisés.")

    run_pipeline(args)


if __name__ == "__main__":
    main()
