"""
app.py — Dossier Carré · Cold Outreach Télécommande
Interface ultra-légère Streamlit → Google Antigravity Webhook.
Aucune logique de scraping embarquée.
"""

import os
import streamlit as st
import requests

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION — Remplir avec l'URL de votre webhook Antigravity
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANTIGRAVITY_WEBHOOK_URL = os.environ.get("ANTIGRAVITY_WEBHOOK_URL", "")

# Timeout en secondes pour la requête vers Antigravity
REQUEST_TIMEOUT = 120

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="Dossier Carré — Analyse Prospect",
    page_icon="◼",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CSS — Esthétique "Apple Glass" minimaliste
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
    /* ── Typographie Google Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

    /* ── Masquer les éléments Streamlit par défaut ── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    [data-testid="stToolbar"] {display: none;}
    [data-testid="stDecoration"] {display: none;}

    /* ── Corps global ── */
    .stApp {
        background: #09090b;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── Titre principal ── */
    h1 {
        font-weight: 600 !important;
        letter-spacing: -0.03em !important;
        color: #fafafa !important;
        font-size: 1.75rem !important;
    }

    /* ── Sous-titre ── */
    .subtitle {
        color: #71717a;
        font-size: 0.9rem;
        font-weight: 300;
        margin-top: -12px;
        margin-bottom: 32px;
        letter-spacing: 0.01em;
    }

    /* ── Champ de saisie ── */
    .stTextInput > div > div > input {
        background: #18181b !important;
        border: 1px solid #27272a !important;
        border-radius: 12px !important;
        color: #fafafa !important;
        padding: 14px 16px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        transition: border-color 0.2s ease;
    }
    .stTextInput > div > div > input:focus {
        border-color: #3f3f46 !important;
        box-shadow: 0 0 0 2px rgba(63, 63, 70, 0.3) !important;
    }
    .stTextInput > div > div > input::placeholder {
        color: #52525b !important;
    }
    .stTextInput label {
        color: #a1a1aa !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.04em !important;
        text-transform: uppercase !important;
    }

    /* ── Bouton principal ── */
    .stButton > button {
        background: #fafafa !important;
        color: #09090b !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 32px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        letter-spacing: 0.01em;
        cursor: pointer;
        transition: all 0.2s ease;
        width: 100%;
    }
    .stButton > button:hover {
        background: #d4d4d8 !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(250, 250, 250, 0.08);
    }
    .stButton > button:active {
        transform: translateY(0);
    }

    /* ── Bloc de résultats ── */
    .result-card {
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 16px;
        padding: 28px;
        margin-top: 24px;
    }
    .result-card h3 {
        color: #fafafa;
        font-size: 1rem;
        font-weight: 500;
        margin-bottom: 16px;
        letter-spacing: -0.01em;
    }
    .result-label {
        color: #71717a;
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 4px;
        margin-top: 16px;
    }
    .result-value {
        color: #e4e4e7;
        font-size: 0.9rem;
        font-weight: 400;
        line-height: 1.6;
        word-wrap: break-word;
    }
    .result-email-block {
        background: #09090b;
        border: 1px solid #27272a;
        border-radius: 12px;
        padding: 20px;
        margin-top: 8px;
        font-family: 'Inter', monospace;
        font-size: 0.85rem;
        color: #d4d4d8;
        line-height: 1.7;
        white-space: pre-wrap;
    }

    /* ── Séparateur fin ── */
    .divider {
        border: none;
        border-top: 1px solid #27272a;
        margin: 20px 0;
    }

    /* ── Alertes Streamlit — surcharge ── */
    .stAlert {
        background: #18181b !important;
        border: 1px solid #27272a !important;
        border-radius: 12px !important;
        color: #a1a1aa !important;
    }

    /* ── Footer discret ── */
    .app-footer {
        text-align: center;
        color: #3f3f46;
        font-size: 0.7rem;
        margin-top: 64px;
        letter-spacing: 0.02em;
    }
</style>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTERFACE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.markdown("", unsafe_allow_html=True)  # spacer
st.title("◼ Dossier Carré")
st.markdown('<p class="subtitle">Analyse de prospect · Cold Outreach intelligent</p>', unsafe_allow_html=True)

# Champ URL
url_input = st.text_input(
    "URL DU SITE PROSPECT",
    placeholder="https://exemple-entreprise-btp.fr",
    label_visibility="visible",
)

# Bouton d'action
launch = st.button("Lancer l'analyse")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOGIQUE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if launch:
    # Validation de la configuration
    if not ANTIGRAVITY_WEBHOOK_URL:
        st.error("⚠ La variable `ANTIGRAVITY_WEBHOOK_URL` n'est pas configurée. "
                 "Ajoutez-la dans les Secrets de Streamlit Cloud.")
        st.stop()

    # Validation de l'URL saisie
    if not url_input or not url_input.strip().startswith("http"):
        st.warning("Veuillez saisir une URL valide commençant par http:// ou https://")
        st.stop()

    url_clean = url_input.strip()

    with st.spinner("Analyse en cours via Antigravity…"):
        try:
            response = requests.post(
                ANTIGRAVITY_WEBHOOK_URL,
                json={"url": url_clean},
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                data = response.json()

                # ── Extraction des données retournées ──
                # Adapter les clés ci-dessous au format exact de votre webhook
                nom = data.get("nom", data.get("company_name", "—"))
                email = data.get("email", data.get("email_contact", "—"))
                dirigeant = data.get("dirigeant", data.get("director", "—"))
                activite = data.get("activite", data.get("activity", "—"))
                friction = data.get("analyse_friction", data.get("friction_analysis", ""))
                draft = data.get("draft_email", data.get("email_draft", ""))
                siren = data.get("siren", "—")
                naf = data.get("naf", data.get("naf_code", "—"))
                site = data.get("site_web", url_clean)

                # ── Affichage des résultats ──
                st.markdown("---")

                # Carte prospect
                st.markdown(f"""
                <div class="result-card">
                    <h3>Prospect identifié</h3>

                    <div class="result-label">Entreprise</div>
                    <div class="result-value">{nom}</div>

                    <div class="result-label">Dirigeant</div>
                    <div class="result-value">{dirigeant}</div>

                    <div class="result-label">Email de contact</div>
                    <div class="result-value"><strong>{email}</strong></div>

                    <hr class="divider">

                    <div class="result-label">SIREN</div>
                    <div class="result-value">{siren}</div>

                    <div class="result-label">Code NAF</div>
                    <div class="result-value">{naf}</div>

                    <div class="result-label">Activité</div>
                    <div class="result-value">{activite}</div>

                    <div class="result-label">Site web</div>
                    <div class="result-value">{site}</div>
                </div>
                """, unsafe_allow_html=True)

                # Analyse de friction
                if friction:
                    st.markdown(f"""
                    <div class="result-card">
                        <h3>Analyse de friction</h3>
                        <div class="result-value">{friction}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Brouillon email
                if draft:
                    st.markdown(f"""
                    <div class="result-card">
                        <h3>Brouillon Cold Email</h3>
                        <div class="result-email-block">{draft}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Bouton copier le brouillon
                if draft:
                    st.code(draft, language=None)

                st.success("Analyse terminée.")

            elif response.status_code == 422:
                st.error("Le webhook a rejeté la requête. Vérifiez le format de l'URL.")
            elif response.status_code == 429:
                st.warning("Limite de requêtes atteinte. Réessayez dans quelques minutes.")
            elif response.status_code >= 500:
                st.error(f"Erreur serveur Antigravity ({response.status_code}). "
                         "Le service est peut-être temporairement indisponible.")
            else:
                st.error(f"Réponse inattendue : {response.status_code}")

        except requests.exceptions.Timeout:
            st.error("⏱ Délai d'attente dépassé. L'analyse prend plus de temps que prévu. "
                     "Réessayez ou vérifiez l'état du flux Antigravity.")
        except requests.exceptions.ConnectionError:
            st.error("Impossible de joindre le webhook Antigravity. "
                     "Vérifiez l'URL ou votre connexion réseau.")
        except requests.exceptions.JSONDecodeError:
            st.error("La réponse du webhook n'est pas au format JSON attendu.")
        except Exception as e:
            st.error(f"Erreur inattendue : {str(e)}")


# ── Footer ──
st.markdown(
    '<p class="app-footer">Dossier Carré · Propulsé par Google Antigravity</p>',
    unsafe_allow_html=True,
)
