import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import re

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide")

# NIEUWE GEGEVENS UIT JE JSON
NEW_CLIENT_EMAIL = "droping-final@dropping2026.iam.gserviceaccount.com"
# De ruwe private key uit je bericht (inclusief de \n tekens)
RAW_JSON_KEY = """-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCmjmyJdooPgSK4\nqzqBm2BXvjvwPV2Yuh5tOQbKlGuqt1eJrz43QscbkuFBvBNMQHs9z7nyys9HRgZB\npsd9KaaIeNVX5fmK2u509EI5Uy2TpEPdpnkguqX1Bq3DMVbSZtSoZfpwLg+tpqyi\nMtr5PH6e36bKVagmROzSjY8UerA+khIDr4Olv9ZJjGivB/1yxoSiSSZvmcQyc0Kk\nEdPH4++QH9H8toK6qtHuBns2dEU2DThK/r6GObtSr+b9QwENUG69lrnJMeGupFJk\nu2OSuDlAoj7pTnNUG/WPJG8HYV7wLP2er5g7/osuYk/aLQSB877P+acNSj5FU1vQ\n1wI349yRAgMBAAECggEABSmdOuIMG7irmjiBfN6zbOjSPAs05VzggE9wEtOopi8e\nZR/D0Ivu9r914LcbDIYjo8n2aCyJ4fpNS5fnL02dEjYXm8y+sEOCuGiRTGxT+XNy\nIJLORpnOdtK1DFuxRp6GGS2nBnbhCMeFqpXjtG2/+X3ycitXRc9lXU3iuVZns9q/\nqAx5NWZAzTd1C7f7lQu+fM4DJSoozEJxwvjUChGDiSsgsJuc++afa83eUQp1v/oJ\n4i6F2Lp15v7ICeK00DU2GNu4NiOXkIsc7OtetNdE9xrHxxVBuk262zH1FN/ocwKP\n69Jw9+/YbJwx93h5AYkVxlhqE8Dct7Eeb8Z9V/GAmQKBgQDYxF3vKHgh0iYeLXa5\nwXGc9JEVJonZH+Yas2yFQuY66th9IpiYFUvczCzY5M3Of7ROErnH98E5Sj0Rvexl\npR7ROahVPfS7asB2wLNWfO6k6rLl3otTb+Wftb4DsI1z3wzqr7/rz79Nl/6n3Dw9\n4UgfYqfuRLAZoqECamUh1YpVSQKBgQDEs5sVAGlwIl1LadMCsVZ53/iAyyB2pzZW\n2MzgY25DN7pwmDtMxNTr+SfM5Qfj3ziflh7+v3R5eBDoqlkmU6IZg2Mg5zKJsi9h\nlVgTXBRuFnugU0SzOHK+RMuQrcz+T73U+eLUb0uHkY3JFWd6DUZnJpiywrfbUJj4\njI9yByj1CQKBgCvRhiuSQraThKEVD6r9L7pKtglQgQ0jJaDAJG/L1j6SurCRDcew\nhmVb4LT3i6LyrcAaiPOjYavzFeVAP0lM163zudOBcrdwHPfkfFw/ZP5xcziEhCWZ\nuRFP69lTF0UVEcdfP6yrkkBdOV01Z/gaUjoF92xy9iY4edPDLi5ovE4BAoGBAMOB\nCFjdae7MGRJFgjcg76R+2c2ZFxEXrUiwfyFfck5Y63PRus7YrBBGOirKUQdJ7Euh\nt/jXbfr1PUkjVyxi37CgCDzBzldRxQoml73WPXAV5JY7bQL8zf8S/Yk1VZRGyZUP\nMUaXv+hk4RnFrm1/GESZ9hdmtbrD5ubTPhfFyg2RAoGAaLqVkPG13Z0bBVyUnSKj\nHHxcPrLHziwGdAoETO9MfVxVWyDcIW7xXcO1myAP2WJJSi5tdzqcwcyEAr94faCV\ngX1WbjYqkhjl0TzkpGyj0QcJuzRrOJPCggaAJrHokPyKvRklGI/a6pc4k5Jb0bFN\nAavRu0PHwhFJmlcLGe8eEDk=\n-----END PRIVATE KEY-----\n"""

def get_clean_key(raw_key):
    # Vervang de tekstuele '\n' door echte enters
    clean = raw_key.replace('\\n', '\n')
    return clean.strip()

SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "dropping2026",
    "private_key_id": "3448edb212d29499e3a16416953a5f72644b762f",
    "private_key": get_clean_key(RAW_JSON_KEY),
    "client_email": NEW_CLIENT_EMAIL,
    "token_uri": "https://oauth2.googleapis.com/token",
}

@st.cache_resource
def get_ss_worksheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
    client = gspread.authorize(creds)
    # Open de sheet (vergeet niet de nieuwe email toegang te geven!)
    sh = client.open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI")
    return sh.worksheet("Data")

try:
    ws = get_ss_worksheet()
    st.success("✅ Verbinding geslaagd met nieuwe Service Account!")
except Exception as e:
    st.error(f"❌ Verbindingsfout: {e}")
    st.info(f"Check of {NEW_CLIENT_EMAIL} toegang heeft tot de Google Sheet.")
    st.stop()

# --- 2. DATA & LOGIN LOGICA ---
def get_db():
    return pd.DataFrame(ws.get_all_records())

def save_to_db(df):
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    team = st.text_input("Teamnaam").strip()
    if st.button("Inloggen"):
        if team == "THOMASBAAS":
            st.session_state.role = "admin"
            st.session_state.logged_in = True
            st.rerun()
        elif team:
            df = get_db()
            if team not in df['Teamnaam'].values:
                new_row = {"Teamnaam": team, "Fase": "START", "Alarm": "GEEN", "Score": 0}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True).fillna(0)
                save_to_db(df)
            st.session_state.team = team
            st.session_state.role = "user"
            st.session_state.logged_in = True
            st.rerun()
else:
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        st.dataframe(get_db())
        if st.button("Log uit"):
            st.session_state.logged_in = False
            st.rerun()
    else:
        st.title(f"Welkom team {st.session_state.team}")
        st.write("De verbinding is stabiel. Klaar voor de start!")
        if st.button("Log uit"):
            st.session_state.logged_in = False
            st.rerun()
