import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium

# --- CONFIG ---
st.set_page_config(page_title="Dropping 2026", layout="wide")
FINISH_COORDS = [51.2435, 4.4452]

def fix_key(key):
    """Schoont de sleutel op en forceert het juiste PEM formaat."""
    if not key:
        return ""
    # Verwijder headers/footers en witruimte om de pure base64 over te houden
    core = key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").strip()
    clean_core = "".join(core.split())
    # Bouw de sleutel opnieuw op met keiharde enters om de 64 tekens
    formatted = "-----BEGIN PRIVATE KEY-----\n"
    for i in range(0, len(clean_core), 64):
        formatted += clean_core[i:i+64] + "\n"
    formatted += "-----END PRIVATE KEY-----\n"
    return formatted

@st.cache_resource
def get_ss_worksheet():
    # Haal info uit secrets
    try:
        secret_info = dict(st.secrets["gcp_service_account"])
        # Fix de private key direct
        secret_info["private_key"] = fix_key(secret_info["private_key"])
        
        creds = Credentials.from_service_account_info(
            secret_info, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        return client.open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").sheet1
    except Exception as e:
        st.error(f"Verbindingsfout: {e}")
        return None

def get_db_as_df():
    ws = get_ss_worksheet()
    if ws is None: return pd.DataFrame()
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame(columns=["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Timer", "Start_Lat", "Start_Lon"])

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws:
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())

# --- LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip()
    l_names = st.text_input("Namen Leden")
    
    if st.button("Start"):
        if t_name == "THOMASBAAS":
            st.session_state.role, st.session_state.logged_in = "admin", True
            st.rerun()
        elif t_name and l_names:
            df = get_db_as_df()
            if t_name not in df['Teamnaam'].astype(str).values:
                new_row = {"Teamnaam": t_name, "Leden": l_names, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": 0, "Timer": "01:00:00", "Start_Lat": 0.0, "Start_Lon": 0.0}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
else:
    # --- ADMIN ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db_as_df()
        st.dataframe(df)
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()
    # --- USER ---
    else:
        st.title(f"Team: {st.session_state.team}")
        # (Rest van je user code hier... ik hou het kort om de fix te testen)
        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()
