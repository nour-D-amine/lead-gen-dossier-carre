# 🧬 GEMINI — Constitution du Projet

> Source de vérité architecturale. Ce fichier définit les schémas de données, les règles de comportement et les invariants qui ne doivent jamais être violés.

---

## 1. Identité du Projet

| Propriété | Valeur |
|---|---|
| **Nom** | Lead Gen BTP — Dossier Carré |
| **Framework** | B.L.A.S.T (Blueprint, Link, Architect, Style, Trigger) |
| **Cible** | PME du BTP en France (NAF 41xx, 42xx, 43xx) |
| **Volume** | 500 — 1000 leads qualifiés |
| **Coût cible** | ~0€ (tiers gratuits APIs) |
| **Source of Truth** | `leads_btp.csv` |

---

## 2. Schéma de Données — CSV Final

```
leads_btp.csv
```

| **Sortie** | Google Sheets | Dashboard d'enrichissement (optimisation Claude Cowork) |
|---|---|---|---|---|
| 1 | `SIREN` | string (9 digits) | Annuaire Entreprises | ✅ |
| 2 | `Nom` | string | Annuaire Entreprises | ✅ |
| 3 | `NAF` | string (code APE) | Annuaire Entreprises | ✅ |
| 4 | `Dirigeant` | string | Pappers | ❌ |
| 5 | `Email` | string | Gemini (extrait du Markdown Firecrawl) | ❌ |
| 6 | `Site Web` | string (URL) | Annuaire Entreprises / Pappers | ❌ |
| 7 | `Activité BOAMP` | string | BOAMP | ❌ |
| 8 | `Analyse Friction` | text | Gemini 2.5 Flash | ❌ |
| 9 | `Draft Email` | text | Gemini 2.5 Flash | ❌ |
| 10 | `Statut Traitement` | string | Valeur par défaut : "À optimiser" | ✅ |

### Règles de validation

- `SIREN` : exactement 9 chiffres, unique dans le fichier
- `NAF` : doit matcher le pattern `4[1-3]\.\d{2}[A-Z]?`
- `Email` : format RFC 5322 valide ou vide
- `Site Web` : URL valide (https préféré) ou vide
- Pas de doublons sur `SIREN`

---

## 3. Règles de Comportement (Invariants)

### 3.1 — Rate Limiting

```
INVARIANT: Aucune API ne doit recevoir plus de requêtes que son quota gratuit.
```

| API | Stratégie | Délai inter-requêtes |
|---|---|---|
| Annuaire Entreprises | Throttle adaptatif | 200ms min |
| Pappers | Batch avec compteur | 1s min + compteur mensuel |
| BOAMP | Throttle conservateur | 500ms min |
| Firecrawl | Budget de crédits | 2s min + compteur total |
| Gemini | Batch par lot de 10 | 2s min |

### 3.2 — Idempotence & Reprise

```
INVARIANT: Le script doit pouvoir être relancé sans créer de doublons.
```

- Checkpoint après chaque batch réussi (fichier `checkpoint.json`)
- Vérification SIREN existant avant insertion
- Mode append-only sur le CSV

### 3.3 — Graceful Degradation

```
INVARIANT: L'absence de données optionnelles ne bloque jamais le pipeline.
```

- Si Pappers échoue → `Dirigeant` = vide, on continue
- Si Firecrawl échoue → `Email` = vide, on continue
- Si BOAMP ne trouve rien → `Activité BOAMP` = "Aucune activité détectée"
- Si Gemini échoue → `Analyse Friction` et `Draft Email` = vides, le lead est quand même enregistré

### 3.4 — Sécurité des Données

```
INVARIANT: Aucune clé API ne doit apparaître dans le code source ou les logs.
```

- Toutes les clés dans `.env` (ajouté au `.gitignore`)
- Logs purgés de tout token/clé avant écriture
- Pas de commit de `.env` ou de données personnelles

---

## 4. Architecture en 3 Couches + MCP

```
┌─────────────────────────────────────────────────────────┐
│                    COUCHE 3 — INTELLIGENCE              │
│         Gemini 2.5 Flash : Analyse + Rédaction          │
│         Input: JSON compilé (BOAMP + Site Markdown)     │
│         Output: Email contact + Friction + Draft email  │
├─────────────────────────────────────────────────────────┤
│                    COUCHE 2 — ENRICHISSEMENT             │
│         Pappers : Dirigeants                            │
│         Firecrawl : Scraping Markdown intégral des sites│
│         BOAMP : Activité marchés publics                │
│         Input: Liste SIREN de la Couche 1               │
│         Output: JSON enrichi par lead                   │
├─────────────────────────────────────────────────────────┤
│                    COUCHE 1 — DATA INGESTION            │
│         Annuaire Entreprises (API) : Extraction batch   │
│         MCP data.gouv.fr : Exploration de catalogue     │
│         Filtres: NAF 41xx/42xx/43xx + Géographie        │
│         Output: Liste de SIREN + données de base        │
└─────────────────────────────────────────────────────────┘
```

### 4.1 — MCP data.gouv.fr (Exploration)

| Propriété | Valeur |
|---|---|
| **Endpoint** | `https://mcp.data.gouv.fr/mcp` |
| **Rôle** | Exploration de catalogue (datasets, APIs, organisations) |
| **Usage** | Découverte de nouvelles sources de données BTP |
| **Extraction batch** | Déléguée à `api_annuaire.py` (API directe) |

---

## 5. Style des Cold Emails — Directives Gemini

### Ton & Positionnement

- **Style** : Apple — institutionnel, minimaliste, direct
- **Longueur** : 5-7 phrases max
- **Angle** : Préservation du "budget cognitif" du dirigeant
- **Hook** : Identifier la fuite d'énergie mentale liée à l'administratif des appels d'offres
- **CTA** : Un seul, clair, sans pression

### Anti-patterns (interdits)

- ❌ Superlatifs ("le meilleur", "révolutionnaire")
- ❌ Formules creuses ("dans un monde en constante évolution")
- ❌ Urgence artificielle ("offre limitée")
- ❌ Jargon marketing ("synergie", "disruption")
- ❌ Tutoiement
- ❌ Emojis

### Structure type

```
[Accroche contextuelle — 1 phrase ciblée sur une friction identifiée]

[Constat factuel — lien avec l'activité BOAMP ou le secteur NAF]

[Proposition de valeur — en 1 phrase, ce qu'on résout concrètement]

[CTA minimaliste — une seule action demandée]

[Signature professionnelle]
```

---

## 6. Arborescence Cible du Projet

```
Lead_dossier_carré/
├── .env                    # Clés API (NON COMMITÉ)
├── .gitignore
├── task_plan.md            # Phases & checklists B.L.A.S.T
├── findings.md             # Recherches & contraintes API
├── progress.md             # Journal d'exécution
├── gemini.md               # CE FICHIER — Constitution
├── requirements.txt        # Dépendances Python
├── main.py                 # Script principal (3 couches)
├── config.py               # Configuration & constantes
├── utils/
│   ├── api_annuaire.py     # Client Annuaire Entreprises
│   ├── api_pappers.py      # Client Pappers
│   ├── api_boamp.py        # Client BOAMP
│   ├── api_firecrawl.py    # Client Firecrawl (Markdown)
│   ├── api_gemini.py       # Client Google GenAI
│   └── rate_limiter.py     # Gestionnaire de rate limiting
├── prompts/
│   └── system_prompt.txt   # System prompt Gemini
├── data/
│   ├── leads_btp.csv       # SOURCE OF TRUTH
│   └── checkpoint.json     # État de reprise
├── logs/
│   └── run_YYYYMMDD.log    # Logs structurés
└── run.sh                  # Script de lancement batch
```
