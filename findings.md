# 🔍 FINDINGS — Recherches, Découvertes & Contraintes API

> Journal de recherche vivant. Chaque découverte est horodatée et sourcée.

---

## APIs Identifiées & Validées

### 1. API Annuaire Entreprises (data.gouv.fr) ✅ VALIDÉE

| Propriété | Valeur |
|---|---|
| Base URL | `https://recherche-entreprises.api.gouv.fr` |
| Endpoint | `GET /search` |
| Auth | Aucune (API publique) |
| Rate Limit | ~7 req/s (non documenté officiellement) |
| Paramètre NAF | `activite_principale` (ex: `43.21A`) |
| Paramètre géo | `departement`, `region`, `code_postal` |
| Pagination | `page` + `per_page` (max 25) |
| Volume test | **9 204 résultats** pour NAF 43.21A seul |

#### 🚨 Découverte majeure (2026-05-14)
L'API retourne **les dirigeants** directement dans les résultats !
```json
"dirigeants": [
  {"nom": "CORTEEL", "prenoms": "STEPHANE", "qualite": "Président du conseil d'administration", "type_dirigeant": "personne physique"},
  {"nom": "JOUVEN", "prenoms": "OLIVIER", "qualite": "Directeur Général", "type_dirigeant": "personne physique"}
]
```
**Impact** : Pappers devient un fallback uniquement, pas une dépendance critique.

#### Champs retournés utiles
- `siren` — identifiant unique
- `nom_complet` — raison sociale
- `activite_principale` — code NAF
- `dirigeants[]` — liste complète avec qualité
- `categorie_entreprise` — "PME", "ETI", "GE"
- `etat_administratif` — "A" (actif) ou "F" (fermé)
- `finances.{annee}.ca` — chiffre d'affaires
- `siege.adresse` — adresse complète
- `siege.code_postal` / `departement` / `region`

#### Attention : paramètre `q`
- `q=*` retourne 0 résultat ❌
- `q=` (vide) ou absent → retourne les résultats filtrés par NAF ✅

---

### 2. API BOAMP (OpenDataSoft) ✅ VALIDÉE

| Propriété | Valeur |
|---|---|
| Base URL | `https://boamp-datadila.opendatasoft.com/api/explore/v2.1` |
| Endpoint | `GET /catalog/datasets/boamp/records` |
| Auth | Aucune (données ouvertes, Licence Ouverte 2.0) |
| Query lang | ODSQL |
| Volume total | **1 666 632 annonces** |
| Rate Limit | Non documenté — throttle conservateur recommandé (500ms) |

#### Champs clés
- `titulaire` — nom du titulaire du marché (peut être null pour les appels d'offres)
- `objet` — description du marché
- `nomacheteur` — nom de l'acheteur public
- `descripteur_libelle` — catégories (ex: "Bâtiment")
- `nature_libelle` — "Avis de marché", "Avis d'attribution"
- `dateparution` — date de publication
- `url_avis` — lien vers l'annonce complète

#### Stratégie de recherche BOAMP
```
# Recherche par titulaire
where=search(titulaire,'NOM_ENTREPRISE')

# Filtrer les 24 derniers mois
where=dateparution >= '2024-05-01'

# Combinaison
where=search(titulaire,'SNEF') AND dateparution >= '2024-05-01'
```

---

### 3. API Pappers ✅ CONFIRMÉE (Fallback)

| Propriété | Valeur |
|---|---|
| Base URL | `https://api.pappers.fr/v2` |
| Endpoint | `GET /entreprise?siren=XXX&api_token=YYY` |
| Auth | Clé API (paramètre `api_token`) |
| Tier gratuit | **100 req/mois** |
| Inscription | https://www.pappers.fr/api/register |

#### Rôle révisé
Fallback uniquement — utilisé quand l'Annuaire Entreprises ne retourne pas de dirigeant.
Données supplémentaires disponibles : CA détaillé, statuts, documents officiels.

---

### 4. API Firecrawl ✅ CONFIRMÉE

| Propriété | Valeur |
|---|---|
| Base URL | `https://api.firecrawl.dev/v1` |
| Endpoint | `POST /scrape` |
| Auth | Bearer token |
| Tier gratuit | **1 000 crédits/mois** |

#### Coûts par opération
| Action | Crédits |
|---|---|
| Scrape basique | 1 crédit/page |
| + Extraction JSON | +4 crédits |
| + Stealth proxy | +4 crédits |

#### Stratégie optimale
- Utiliser le scrape basique (1 crédit) + extraction regex côté client pour les emails
- Éviter l'extraction JSON Firecrawl (+4 crédits) → trop coûteux
- Budget : 1000 crédits = **1000 sites scrapés** en mode basique

---

### 5. API Anthropic (Claude Sonnet 4.6) ✅ CONFIRMÉE

| Propriété | Valeur |
|---|---|
| Base URL | `https://api.anthropic.com/v1` |
| Endpoint | `POST /messages` |
| Model ID | `claude-sonnet-4-6` |
| Auth | Header `x-api-key` |
| Input | $3.00 / M tokens |
| Output | $15.00 / M tokens |
| Batch API | **-50% sur les prix** |

#### Estimation de coûts
- ~500 tokens input par lead (JSON contexte)
- ~300 tokens output par lead (analyse + email)
- 500 leads → 250K input + 150K output
- **Coût estimé : $0.75 input + $2.25 output = ~$3 total**
- Avec Batch API : **~$1.50 total**

---

## Codes NAF Ciblés (35 codes)

| Code | Libellé |
|---|---|
| 41.10A | Promotion immobilière de logements |
| 41.10B | Promotion immobilière de bureaux |
| 41.10C | Promotion immobilière d'autres bâtiments |
| 41.10D | Supports juridiques de programmes |
| 41.20A | Construction de maisons individuelles |
| 41.20B | Construction d'autres bâtiments |
| 42.11Z | Construction de routes et autoroutes |
| 42.12Z | Construction de voies ferrées |
| 42.13A | Construction d'ouvrages d'art |
| 42.13B | Construction et entretien de tunnels |
| 42.21Z | Construction de réseaux pour fluides |
| 42.22Z | Construction de réseaux électriques et télécoms |
| 42.91Z | Construction d'ouvrages maritimes et fluviaux |
| 42.99Z | Construction d'autres ouvrages de génie civil |
| 43.11Z | Travaux de démolition |
| 43.12A | Travaux de terrassement courants |
| 43.12B | Travaux de terrassement spécialisés |
| 43.13Z | Forages et sondages |
| 43.21A | Travaux d'installation électrique |
| 43.22A | Travaux d'installation d'eau et de gaz |
| 43.22B | Travaux d'installation thermique et climatisation |
| 43.29A | Travaux d'isolation |
| 43.31Z | Travaux de plâtrerie |
| 43.32A | Travaux de menuiserie bois et PVC |
| 43.32B | Travaux de menuiserie métallique et serrurerie |
| 43.33Z | Travaux de revêtement des sols et des murs |
| 43.34Z | Travaux de peinture et vitrerie |
| 43.39Z | Autres travaux de finition |
| 43.91A | Travaux de charpente |
| 43.91B | Travaux de couverture par éléments |
| 43.99A | Travaux d'étanchéification |
| 43.99B | Travaux de montage de structures métalliques |
| 43.99C | Travaux de maçonnerie générale et gros œuvre |
| 43.99D | Autres travaux spécialisés de construction |
| 43.99E | Location avec opérateur de matériel de construction |

---

## Contraintes Techniques Mises à Jour

- [x] **Annuaire Entreprises** : Dirigeants disponibles directement → Pappers en fallback
- [x] **Pappers** : 100 req/mois gratuit confirmé → budget critique à gérer
- [x] **BOAMP** : API OpenDataSoft fonctionnelle, recherche par titulaire validée
- [x] **Firecrawl** : 1000 crédits/mois → scrape basique à 1 crédit = 1000 sites
- [x] **Anthropic** : ~$1.50-$3 total pour 500 leads → budget acceptable

---

## Découvertes & Notes

### 2026-05-14 — Smoke Tests API Live

**Annuaire Entreprises** : Requête `GET /search?activite_principale=43.21A&departement=75` retourne 9 204 résultats avec dirigeants inclus. Le paramètre `q` doit être vide ou absent (pas `*`).

**BOAMP** : Requête `GET /records?limit=3` retourne des résultats avec la structure complète. Le champ `titulaire` est souvent null pour les appels d'offres (normal — seulement rempli pour les avis d'attribution).

**Observation clé** : Les résultats Annuaire contiennent des entreprises GE (Grandes Entreprises) comme SNEF ou Eiffage. Il faudra filtrer sur `categorie_entreprise` pour cibler les PME.
