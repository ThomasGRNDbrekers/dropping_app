import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026 - Master Control", layout="wide")

PRIVATE_KEY = r"""-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCmjmyJdooPgSK4
qzqBm2BXvjvwPV2Yuh5tOQbKlGuqt1eJrz43QscbkuFBvBNMQHs9z7nyys9HRgZB
psd9KaaIeNVX5fmK2u509EI5Uy2TpEPdpnkguqX1Bq3DMVbSZtSoZfpwLg+tpqyi
Mtr5PH6e36bKVagmROzSjY8UerA+khIDr4Olv9ZJjGivB/1yxoSiSSZvmcQyc0Kk
EdPH4++QH9H8toK6qtHuBns2dEU2DThK/r6GObtSr+b9QwENUG69lrnJMeGupFJk
u2OSuDlAoj7pTnNUG/WPJG8HYV7wLP2er5g7/osuYk/aLQSB877P+acNSj5FU1vQ
1wI349yRAgMBAAECggEABSmdOuIMG7irmjiBfN6zbOjSPAs05VzggE9wEtOopi8e
ZR/D0Ivu9r914LcbDIYjo8n2aCyJ4fpNS5fnL02dEjYXm8y+sEOCuGiRTGxT+XNy
IJLORpnOdtK1DFuxRp6GGS2nBnbhCMeFqpXjtG2/+X3ycitXRc9lXU3iuVZns9q/
qAx5NWZAzTd1C7f7lQu+fM4DJSoozEJxwvjUChGDiSsgsJuc++afa83eUQp1v/oJ
4i6F2Lp15v7ICeK00DU2GNu4NiOXkIsc7OtetNdE9xrHxxVBuk262zH1FN/ocwKP
69Jw9+/YbJwx93h5AYkVxlhqE8Dct7Eeb8Z9V/GAmQKBgQDYxF3vKHgh0iYeLXa5
wXGc9JEVJonZH+Yas2yFQuY66th9IpiYFUvczCzY5M3Of7ROErnH98E5Sj0Rvexl
pR7ROahVPfS7asB2wLNWfO6k6rLl3otTb+Wftb4DsI1z3wzqr7/rz79Nl/6n3Dw9
4UgfYqfuRLAZoqECamUh1YpVSQKBgQDEs5sVAGlwIl1LadMCsVZ53/iAyyB2pzZW
2MzgY25DN7pwmDtMxNTr+SfM5Qfj3ziflh7+v3R5eBDoqlkmU6IZg2Mg5zKJsi9h
nlVgTXBRuFnugU0SzOHK+RMuQrcz+T73U+eLUb0uHkY3JFWd6DUZnJpiywrfbUJj4
jI9yByj1CQKBgCvRhiuSQraThKEVD6r9L7pKtglQgQ0jJaDAJG/L1j6SurCRDcew
hmVb4LT3i6LyrcAaiPOjYavzFeVAP0lM163zudOBcrdwHPfkfFw/ZP5xcziEhCWZ
uRFP69lTF0UVEcdfP6yrkkBdOV01Z/gaUjoF92xy9iY4edPDLi5ovE4BAoGBAMOB
CFjdae7MGRJFgjcg76R+2c2ZFxEXrUiwfyFfck5Y63PRus7YrBBGOirKUQdJ7Euh
t/jXbfr1PUkjVyxi37CgCDzBzldRxQoml73WPXAV5JY7bQL8zf8S/Yk1VZRGyZUP
MUaXv+hk4RnFrm1/GESZ9hdmtbrD5ubTPhfFyg2RAoGAaLqVkPG13Z0bBVyUnSKj
HHxcPrLHziwGdAoETO9MfVxVWyDcIW7xXcO1myAP2WJJSi5tdzqcwcyEAr94faCV
gX1WbjYqkhjl0TzkpGyj0QcJuzRrOJPCggaAJrHokPyKvRklGI/a6pc4k5Jb0bFN
AavRu0PHwhFJmlcLGe8eEDk=
-----END PRIVATE KEY-----"""

FINISH_COORDS = [51.2435, 4.4452]

@st.cache_resource
def get_ss_worksheet():
    info = {
        "type": "service_account",
        "project_id": "dropping2026",
        "private_key": PRIVATE_KEY.replace('\\n', '\n'),
        "client_email": "droping-final@dropping2026.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds).open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").worksheet("Data")

def get_db():
    try:
        return pd.DataFrame(get_ss_worksheet().get_all_records())
    except:
        return pd.DataFrame(columns=["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Timer", "Start_Lat", "Start_Lon"])

def save_to_db(df):
    ws = get_ss_worksheet()
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

# --- 2. AUTH & REFRESH ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip()
    l_names = st.text_input("Namen Leden")
    if st.button("Start Dropping"):
        if t_name == "THOMASBAAS":
            st.session_state.role, st.session_state.logged_in = "admin", True
            st.rerun()
        elif t_name and l_names:
            df = get_db()
            if t_name not in df['Teamnaam'].values:
                new = {"Teamnaam": t_name, "Leden": l_names, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": 0, "Timer": "01:00:00", "Start_Lat": 0.0, "Start_Lon": 0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True).fillna(0)
                save_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
else:
    # --- 3. ADMIN PANEL (CONTROL ROOM) ---
    if st.session_state.role == "admin":
        st.components.v1.html("<script>setTimeout(function(){window.location.reload();}, 30000);</script>", height=0)
        st.title("🕹️ Control Room (Admin)")
        df = get_db()
        st.write("### Live Status Teams")
        st.dataframe(df, use_container_width=True)
        
        if not df.empty:
            st.divider()
            target = st.selectbox("Selecteer een team om aan te sturen:", df['Teamnaam'].unique())
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("🚨 Opdrachten & Alarmen")
                preset_msg = st.selectbox("Kies een voorgeprepte opdracht:", [
                    "Eigen invoer...", 
                    "🚨 BACK ON TRACK! Jullie wijken te ver af.", 
                    "📸 FOTO OPDRACHT: Maak een selfie met een lantaarnpaal.", 
                    "🧩 RAADSEL: Wat heeft een oog maar kan niet zien?", 
                    "⏱️ SPEEDRUN: Loop 500m in een rechte lijn!",
                    "🛑 STOP! Blijf 2 minuten staan voor extra punten."
                ])
                custom_msg = st.text_input("Of typ zelf een bericht:")
                final_msg = custom_msg if custom_msg else preset_msg
                
                if st.button("Push naar Team"):
                    df.loc[df['Teamnaam'] == target, 'Alarm'] = final_msg
                    save_to_db(df); st.success("Verzonden!")

            with col2:
                st.subheader("⏱️ Timer Aanpassen")
                new_t = st.text_input("Nieuwe tijd (HH:MM:SS)", value="00:45:00")
                if st.button("Update Klok"):
                    df.loc[df['Teamnaam'] == target, 'Timer'] = new_t
                    save_to_db(df); st.success("Tijd bijgewerkt!")

            with col3:
                st.subheader("🏆 Scorebord")
                new_s = st.number_input("Nieuwe score", value=0)
                if st.button("Update Punten"):
                    df.loc[df['Teamnaam'] == target, 'Score'] = new_s
                    save_to_db(df); st.success("Score aangepast!")
        
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

    # --- 4. TEAM DASHBOARD (DEELNEMERS) ---
    else:
        st.components.v1.html("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", height=0)
        df = get_db()
        my_data = df[df['Teamnaam'] == st.session_state.team].iloc[0]

        # Alarm scherm (Blokkeert de rest)
        if str(my_data['Alarm']) != "GEEN":
            st.warning("### 🔔 NIEUWE BOODSCHAP VAN DE LEIDING")
            st.error(f"## {my_data['Alarm']}")
            if st.button("BEVESTIG ONTVANGST / KLAAR"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                save_to_db(df); st.rerun()
            st.stop()

        st.title(f"Team: {st.session_state.team}")
        c1, c2 = st.columns(2)
        c1.metric("⏳ Tijd Over", my_data['Timer'])
        c2.metric("🏆 Punten", f"{my_data['Score']} Pnt")

        # FASE 1: Startpositie bepalen
        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.subheader("Waar zijn jullie gedropt?")
            st.info("Zoek jullie geschatte locatie op de kaart en klik erop.")
            m = folium.Map(location=[51.2194, 4.4025], zoom_start=12)
            st_data = st_folium(m, width="100%", height=450)
            
            if st_data and st_data['last_clicked']:
                lat, lon = st_data['last_clicked']['lat'], st_data['last_clicked']['lng']
                if st.button(f"Bevestig Startpunt: {round(lat,3)}, {round(lon,3)}"):
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lat'] = lat
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lon'] = lon
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "DROPPING"
                    save_to_db(df); st.rerun()
        
        # FASE 2: De Dropping Route
        else:
            st.subheader("🗺️ Jullie Koers")
            start = [my_data['Start_Lat'], my_data['Start_Lon']]
            
            m = folium.Map(location=start, zoom_start=14)
            folium.Marker(start, tooltip="Jullie Gekozen Start", icon=folium.Icon(color='blue', icon='home')).add_to(m)
            folium.Marker(FINISH_COORDS, tooltip="DE FINISH", icon=folium.Icon(color='red', icon='flag')).add_to(m)
            
            # De Rechte Optimale Lijn (Altijd zichtbaar na startkeuze)
            folium.PolyLine([start, FINISH_COORDS], color="blue", weight=4, opacity=0.8, dash_array='10', tooltip="Optimale Route").add_to(m)
            
            st_folium(m, width="100%", height=500)
            st.caption("De stippellijn geeft de kortste route naar de finish aan.")

        if st.button("Uitloggen"): st.session_state.logged_in = False; st.rerun()
