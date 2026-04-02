import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt
import re

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide")

# Deze functie zorgt dat de sleutel ALTIJD het juiste formaat heeft, 
# hoe slordig het ook geplakt is.
def get_clean_key(raw_key):
    # Verwijder headers/footers als die er per ongeluk dubbel in staan
    core = raw_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "")
    # Verwijder ALLE witruimte (spaties, enters, tabs)
    core = re.sub(r'\s+', '', core)
    # Zet de officiële PEM structuur eromheen
    return f"-----BEGIN PRIVATE KEY-----\n{core}\n-----END PRIVATE KEY-----\n"

# DE SLEUTEL: Plak hieronder je sleutel. 
# Zelfs als er enters of spaties tussen staan, de code hierboven wast het schoon.
MY_SECRET_KEY = """
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDFPr2jz214sdnZ
aOYDhviCBsAmny1/iZhwEe45+uw25953vRSpUXf5fsLF6OHtZSxNR+IGqANRp0BV
qgrK7X/ytpFQitfMelMDnKrKfnGqhOpJPGrO52z8+OpKGOQPXMSZmjRd79US3cjB
m24C8igLh3tLuFL0LbGG/GPN2LpBQ8/7zAp1Xo6x82gMrGCy1PEEQyqm/YrKOBCk
nJDBPz/CDIvDSzIIXOrwnz9x/P5eqvynFJrO5v9Kye+xH7Os14BtG7Q24GF92GG4
2FR4F2FCHb5nH6msLCdUX3iYC+6mTmJnPpVEqnQqSmILfuw/+20t9K887nSxiPmh
0PSdr30tAgMBAAECggEAD//rSfd4Ybm1hONI2IDmisTplHMa3Eqo7PBQvW8bTEc0
iSHIjwUpgPlqwGXdYRBw+UeAhWSJY7fNf2q8FjgRMKWQCzM+rDAWU0eY+rTVMLfi
5ElsauJOuYTRxmxsoCAONN0owcpDo6njZWxfo7QJEl8Cne1dUerHSNPoyZ4QBQf1
SFjMs2TZYl16DtwuQmmQ4PYvodaBhqtVGZjFaizGHu3BXjZT2kTojGakQz9qQd+l
nrJSo8iJG+4xt4htt8QQys6AK6t9JSWIVnbfScM79dJY3CqlV/0QAQ2tz7TGlGguN
vmlyWMyyTiH6l+ypLSYMe8TPQSaiaVUQ1/i9SgHrEQKBgQD3gib6kKYLSr1stsVx
qNMsQiXircrDnZB9bQc/y0zVHBmRl30cOttAhk5ibCozbMgCT1Rz+vi7DEmquR57
cdLDB8dbtBoOJzeGB7pexqkOXifRwFzipJLvfrQ7y+VPk2kC0TIYsDdAF2syAKaH
YYQVXfeXIx9axwBYrhsKFHnSUQKBgQDMAyEnNSJrIWArf8k9bqMDG0ml7JU6GxKQ
nbneLHITFkpWd9VsDjRPdAQrRJEHfLSvEXHpUHLo7kYWU9S49KkQAgV9Y53mBZS13
CSkoBYfA3MsUZdxeXcTxL5n0/HSmzTswZzZPOrjCZOxvh0Fmm5dQ6z4jsC06B5Sr
1VkyHJOKHQKBgQCGTOgro9uFWwvH9rDSSKI1bLsz8cuJM3EYrdV2JzFMnc+98W5g
qAsaSwYzX6/ScZ9hqXwQ5siabkN20LYak5uiWhEx0Fsm/N6i6oSVMsS+2BZROUjt
bhGQxLa1j6Cg+kLL1YmSXePM8ignXLT/1skd8vwK1XMJBdxJQkfHw26K0QKBgAYy
piQxygzlI63OoQd7v/oNLyyaRmJQhjzbDkisoh/6dw8ocA5oj8zsBi8aYeHs1mKN
nyK2bfdDnd95xoGj9SrmVNJdX2Ookb8ApCBYOLPSgAI9rFMnNIXmOT6gQr16N55lt
2UmI6CoHtOMigcsjOPKdYvLknEsiBdM+lQofsh/FAoGBAKfZniAjAVKSqUJ8ivqu
8qAnnIE6af3T2i7zHmyJPuj6fMlUPuQyuUhjOosxstHFrlDYUP2uuVbQhGxU4Pve
w1ApbCpYLI6kF2b1M6xGKvT4iIdSWjtIZThoYrDUGITIqtiFUFox+9DICfX8h90z
8LrBdsW6x75evTZx5kdH/pax
"""

SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "dropping2026",
    "private_key_id": "ff7a191a74fb7123d318f50728b527dcfc09bcc9",
    "private_key": get_clean_key(MY_SECRET_KEY),
    "client_email": "dropping2026@dropping2026.iam.gserviceaccount.com",
    "token_uri": "https://oauth2.googleapis.com/token",
}

@st.cache_resource
def get_ss_worksheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI")
    return sh.worksheet("Data")

try:
    ws = get_ss_worksheet()
except Exception as e:
    st.error(f"⚠️ Verbindingsfout: {e}")
    st.stop()

# --- 2. DATA FUNCTIES ---
def get_db():
    return pd.DataFrame(ws.get_all_records())

def save_to_db(df):
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

# --- 3. UI & INLOGGEN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    team = st.text_input("Teamnaam").strip()
    
    if st.button("Start"):
        if team == "THOMASBAAS":
            st.session_state.role = "admin"
            st.session_state.logged_in = True
            st.rerun()
        elif team:
            df = get_db()
            if team not in df['Teamnaam'].values:
                new_row = {"Teamnaam": team, "Fase": "START", "Alarm": "GEEN", "Score": 0}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_to_db(df)
            st.session_state.team = team
            st.session_state.role = "user"
            st.session_state.logged_in = True
            st.rerun()
else:
    # --- ADMIN PAGINA ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db()
        st.dataframe(df)
        if st.button("Uitloggen"):
            st.session_state.logged_in = False
            st.rerun()
    # --- USER PAGINA ---
    else:
        st.title(f"Team: {st.session_state.team}")
        st.success("Verbinding met Google Sheets is gelukt!")
        if st.button("Uitloggen"):
            st.session_state.logged_in = False
            st.rerun()
