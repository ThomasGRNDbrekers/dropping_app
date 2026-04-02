import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt
import re

# --- 1. CONFIGURATIE & SETUP ---
st.set_page_config(page_title="Dropping 2026", layout="wide", initial_sidebar_state="collapsed")

# Jouw nieuwe Service Account gegevens
CLIENT_EMAIL = "droping-final@dropping2026.iam.gserviceaccount.com"
# De RAW key zoals hij uit de JSON kwam (met de \n tekens)
RAW_KEY = r"-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCmjmyJdooPgSK4\nqzqBm2BXvjvwPV2Yuh5tOQbKlGuqt1eJrz43QscbkuFBvBNMQHs9z7nyys9HRgZB\npsd9KaaIeNVX5fmK2u509EI5Uy2TpEPdpnkguqX1Bq3DMVbSZtSoZfpwLg+tpqyi\nMtr5PH6e36bKVagmROzSjY8UerA+khIDr4Olv9ZJjGivB/1yxoSiSSZvmcQyc0Kk\nEdPH4++QH9H8toK6qtHuBns2dEU2DThK/r6GObtSr+b9QwENUG69lrnJMeGupFJk\nu2OSuDlAoj7pTnNUG/WPJG8HYV7wLP2er5g7/osuYk/aLQSB877P+acNSj5FU1vQ\n1wI349yRAgMBAAECggEABSmdOuIMG7irmjiBfN6zbOjSPAs05VzggE9wEtOopi8e\nZR/D0Ivu9r914LcbDIYjo8n2aCyJ4fpNS5fnL02dEjYXm8y+sEOCuGiRTGxT+XNy\nIJLORpnOdtK1DFuxRp6GGS2nBnbhCMeFqpXjtG2/+X3ycitXRc9lXU3iuVZns9q/\nqAx5NWZAzTd1C7f7lQu+fM4DJSoozEJxwvjUChGDiSsgsJuc++afa83eUQp1v/oJ\n4i6F2Lp15v7ICeK00DU2GNu4NiOXkIsc7OtetNdE9xrHxxVBuk262zH1FN/ocwKP\n69Jw9+/YbJwx93h5AYkVxlhqE8Dct7Eeb8Z9V/GAmQKBgQDYxF3vKHgh0iYeLXa5\nwXGc9JEVJonZH+Yas2yFQuY66th9IpiYFUvczCzY5M3Of7ROErnH98E5Sj0Rvexl\npR7ROahVPfS7asB2wLNWfO6k6rLl3otTb+Wftb4DsI1z3wzqr7/rz79Nl/6n3Dw9\n4UgfYqfuRLAZoqECamUh1YpVSQKBgQDEs5sVAGlwIl1LadMCsVZ53/iAyyB2pzZW\n2MzgY25DN7pwmDtMxNTr+SfM5Qfj3ziflh7+v3R5eBDoqlkmU6IZg2Mg5zKJsi9h\nlVgTXBRuFnugU0SzOHK+RMuQrcz+T73U+eLUb0uHkY3JFWd6DUZnJpiywrfbUJj4\njI9yByj1CQKBgCvRhiuSQraThKEVD6r9L7pKtglQgQ0jJaDAJG/L1j6SurCRDcew\nhmVb4LT3i6LyrcAaiPOjYavzFeVAP0lM163zudOBcrdwHPfkfFw/ZP5xcziEhCWZ\nuRFP69lTF0UVEcdfP6yrkkBdOV01Z/gaUjoF92xy9iY4edPDLi5ovE4BAoGBAMOB\nCFjdae7MGRJFgjcg76R+2c2ZFxEXrUiwfyFfck5Y63PRus7YrBBGOirKUQdJ7Euh\nt/jXbfr1PUkjVyxi37CgCDzBzldRxQoml73WPXAV5JY7bQL8zf8S/Yk1VZRGyZUP\nMUaXv+hk4RnFrm1/GESZ9hdmtbrD5ubTPhfFyg2RAoGAaLqVkPG13Z0bBVyUnSKj\nHHxcPrLHziwGdAoETO9MfVxVWyDcIW7xXcO1myAP2WJJSi5tdzqcwcyEAr94faCV\ngX1WbjYqkhjl0TzkpGyj0QcJuzRrOJPCggaAJrHokPyKvRklGI/a6pc4k5Jb0bFN\nAavRu0PHwhFJmlcLGe8eEDk=\n-----END PRIVATE KEY-----"

def fix_key(key_string):
    # Vervang tekstuele \n door echte enters en strip witruimte
    return key_string.replace(r'\n', '\n').replace('\\n', '\n').strip()

SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "dropping2026",
    "private_key": fix_key(RAW_KEY),
    "client_email": CLIENT_EMAIL,
    "token_uri": "https://oauth2.googleapis.com/token",
}

@st.cache_resource
def get_ss_worksheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI")
    return sh.worksheet("Data")

# --- 2. DATA FUNCTIES ---
def get_db():
    ws = get_ss_worksheet()
    return pd.DataFrame(ws.get_all_records())

def save_to_db(df):
    ws = get_ss_worksheet()
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat, dLon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    return R * 2 * asin(sqrt(a))

FINISH_COORDS = (51.2435, 4.4452)

# --- 3. SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'team' not in st.session_state:
    st.session_state.team = None

# --- 4. UI: LOGIN SCHERM ---
if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    st.subheader("Welkom bij de dropping! Log in met je teamnaam.")
    
    team_input = st.text_input("Teamnaam").strip()
    leden_input = st.text_input("Namen van de leden")
    
    if st.button("Start de Dropping"):
        if team_input == "THOMASBAAS":
            st.session_state.role = "admin"
            st.session_state.logged_in = True
            st.rerun()
        elif team_input and leden_input:
            try:
                df = get_db()
                if team_input not in df['Teamnaam'].values:
                    new_row = {
                        "Teamnaam": team_input, "Leden": leden_input, 
                        "Fase": "START", "Alarm": "GEEN", "Score": 0,
                        "Huidige_Lat": 0.0, "Huidige_Lon": 0.0
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    save_to_db(df)
                
                st.session_state.team = team_input
                st.session_state.role = "user"
                st.session_state.logged_in = True
                st.rerun()
            except Exception as e:
                st.error(f"Verbindingsfout: {e}")
        else:
            st.warning("Vul aub een teamnaam en de namen van de leden in.")

# --- 5. UI: ADMIN PANEL ---
elif st.session_state.role == "admin":
    st.title("🕹️ Control Room (Admin)")
    
    if st.button("Uitloggen"):
        st.session_state.logged_in = False
        st.rerun()
    
    df = get_db()
    st.write("### Live Team Overzicht")
    st.dataframe(df, use_container_width=True)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🚨 Alarm Versturen")
        target_team = st.selectbox("Kies Team", df['Teamnaam'].unique())
        bericht = st.text_input("Bericht (bijv. 'Loop terug!')")
        if st.button("Verstuur Alarm"):
            df.loc[df['Teamnaam'] == target_team, 'Alarm'] = bericht
            save_to_db(df)
            st.success(f"Alarm verzonden naar {target_team}!")

    with col2:
        st.subheader("🏆 Score Aanpassen")
        target_score = st.selectbox("Kies Team ", df['Teamnaam'].unique())
        nieuwe_score = st.number_input("Nieuwe Score", value=0)
        if st.button("Update Score"):
            df.loc[df['Teamnaam'] == target_score, 'Score'] = nieuwe_score
            save_to_db(df)
            st.success("Score bijgewerkt!")

# --- 6. UI: TEAM DASHBOARD ---
else:
    df = get_db()
    my_data = df[df['Teamnaam'] == st.session_state.team].iloc[0]
    
    st.title(f"Team: {st.session_state.team}")
    
    # Check voor Alarmen
    if my_data['Alarm'] != "GEEN":
        st.error(f"### 🚨 BERICHT VAN DE LEIDING:\n{my_data['Alarm']}")
        if st.button("Ik heb het begrepen"):
            df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
            save_to_db(df)
            st.rerun()

    # Statistieken bovenin
    c1, c2, c3 = st.columns(3)
    c1.metric("Status", my_data['Fase'])
    c2.metric("Score", f"{my_data['Score']} pnt")
    
    # Afstand berekenen (fictief startpunt voor demo, vervang door GPS)
    dist = haversine(51.2194, 4.4025, FINISH_COORDS[0], FINISH_COORDS[1])
    c3.metric("Afstand tot Finish", f"{round(dist, 2)} km")

    # De Kaart
    st.subheader("📍 Jullie Locatie")
    m = folium.Map(location=[51.2194, 4.4025], zoom_start=14)
    folium.Marker(FINISH_COORDS, tooltip="FINISH", icon=folium.Icon(color='red', icon='flag')).add_to(m)
    st_folium(m, width="100%", height=400)

    if st.button("Log uit"):
        st.session_state.logged_in = False
        st.rerun()
