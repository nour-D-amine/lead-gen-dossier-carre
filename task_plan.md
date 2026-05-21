# 📋 TASK PLAN — Lead Gen BTP B.L.A.S.T

> **North Star** : Script autonome d'extraction, d'analyse de frictions et de rédaction de cold emails ultra-personnalisés pour 500-1000 PME du BTP (NAF 41xx/42xx/43xx).

---

## Phase 1 : [B]lueprint — Vision & Logique

- [ ] Cartographier les endpoints de chaque API (Annuaire Entreprises, Pappers, Firecrawl, BOAMP, Anthropic)
- [ ] Définir le schéma de données du CSV final (`leads_btp.csv`)
- [ ] Documenter les rate limits et quotas gratuits de chaque API
- [ ] Spécifier le flow déterministe complet (diagramme de séquence)
- [ ] Définir les règles de retry et de circuit-breaker

## Phase 2 : [L]ink — Connexions

- [ ] Créer le fichier `.env` avec les variables requises
- [ ] Valider l'endpoint Annuaire Entreprises (GET /search — pas de clé requise)
- [x] Extraction de base (SIREN, Nom, Dirigeants) opérationnelle
- [x] PIVOT: Remplacement de Kimi/Claude par Gemini Pro natif.
- [x] PIVOT: Modification de Firecrawl pour extraire du Markdown brut.
- [x] Logique d'envoi SMTP (Nodemailer / Plain Text)
- [x] Mapping CRM Notion (Propriétés + Blocks de contenu)
- [ ] Valider Anthropic Claude Sonnet 4.6 (clé API)
- [ ] Smoke test de chaque endpoint (1 requête de validation)

## Phase 3 : [A]rchitect — Architecture en 3 couches

- [ ] **Couche 1 — Data Ingestion** : Script de fetch Annuaire Entreprises avec filtres NAF + géo
- [ ] **Couche 2 — Enrichissement** : Boucle Pappers (dirigeants) + Firecrawl (sites web) + BOAMP (activité marchés publics)
- [ ] **Couche 3 — Intelligence** : Prompt Claude Sonnet 4.6 pour analyse de frictions + rédaction emails
- [ ] Implémentation du batching et gestion des erreurs 429
- [ ] Logging structuré (JSON) pour traçabilité complète
- [ ] Checkpointing : reprise après interruption sans doublons

## Phase 4 : [S]tyle — Stylisation & Formattage

- [ ] Rédiger le system prompt Claude (style Apple, budget cognitif, fuites d'énergie mentale)
- [ ] Définir le template d'email institutionnel minimaliste
- [ ] Formater le CSV final avec les 9 colonnes requises
- [ ] Valider la qualité des emails générés sur un échantillon de 5 leads

## Phase 5 : [T]rigger — Déclenchement

- [ ] Script de lancement `run.sh` avec traitement par batchs
- [ ] Configuration des délais inter-batchs (respect rate limits)
- [ ] Mode dry-run pour tester sans consommer de quotas API
- [ ] Documentation d'utilisation finale

---

## Métriques de succès

| Métrique | Cible |
|---|---|
| Leads extraits | 500 — 1000 |
| Taux de complétion des données | > 80% |
| Erreurs API 429 | 0 en production |
| Coût total | ~ 0€ (tiers gratuits) |
| Temps d'exécution | < 2h pour 500 leads |
