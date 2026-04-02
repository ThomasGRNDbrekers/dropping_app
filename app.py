import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import base64
import re

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide")

# De sleutel (nu extra gecontroleerd op vreemde tekens)
B64_KEY = "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUV2UUlCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktjd2dnU2pBZ0VBQW9JQkFRQ21qbXlKZG9vUGdTSzQKcXpxQm0yQlh2anZ3UFYyWXVINTVPUWJLbEd1cXQxZUpyejQzUXNjYmt1RkJ2Qk5NUUhzOXo3bnl5czlIUmdaYgpwc2Q5S2FhSWVOVlg1Zm1LMnU1MDlFSTVVeTJUcEVQZHBua2d1cVgxQnEzRE1WYlRadG9aZnB3TGcrdHBxeWkKTXRyNVBINmUzNmJLVmFnbVJPU1NqWThVZXJBK2toSURyNE9sdjlaSmpHaXZCLzF5eG9TaVNTWnZtYVF5YzBLawpFZFBITDkrUUg5SDh0b0s2cXRIdUJuczJkRVUyRFRoS29yNkdPYnRTcitiOVF3RU5VRzY5bHJuSk1lR3VwRkprCnUyT1N1RGxBb2o3cFRuTlVHL1dQSkc4SFlWN3dMUDJlcjVnNy9vc3VZa3RhTFFTQjg3N1ArYWNOU2o1RlUxdlEKMXdJMzQ5eVJBZ01CQUFFQ2dnRUFCU21kT3VJTUc3aXJtamlCZk42emJPalNQQXMwNVZ6Z2dFOXdFdE9vcGk4ZQpaUi9EMEl2dTlyOTRMY2JESVlqbzhuMmFDeUo0ZnBOUzVmbkwwMmRFallYbTh5K3NFT0N1R2lSVGdYVCtYTnkKSUpMT1Jwbk9kdEsxREZ1eFJwNkdHUzJuQm5iaENNZUZxcFhqdEcyLytYM3ljaXRYUWM5bFhVM2l1VlpuczlxLwpxQXg1TldaQXpUZDFDN2Y3bFF1K2ZNNERKU29velVKeHd2alVDaEdEaVNzZ3NKdWMrK2FmYTgzZVVQMXYvYm9KNEk2RjJMcDE1djdJQ2VLMDBEVTJETnU0TmlPWGtJc2M3T3RldE5kRTl4ckh4eFZCdWsyNjJ6SDFGTi9vY3dLUAo2OUp3OSsvWWJKd3g5M2g1QVlrVnhocUVFY3Q3RWViOFo5Vi9HQW1RS0JnUURZeEYzdktIZ2gwaVllTFhhNQp3WEdjOUpFVkpvalpIK1lhczJ5RlF1WTY2dGhJcGlZRlZ2Y3pZNU0zT2Y3Uk9Fcm5IOThFNVNqMFJ2ZXhsCnBSN1JPYWhWUGZTN2FzQjJ3TE5XZk82azZyTGwzY3RUYitXZnRiNERzSTEzd3pqcjc3cnpXNzlpM0R3OQo0VWdmWXFmdVJMQVpvcUVDYW1VaDFZcFZTUUtCZ1FERXNzc1ZBR2x3SWwxTGFkTUNWVlo1My9pQXl5QjJwelpXclpNemdZMjVETjdwd21EdE14TlRyK1NmTTVRZmozemlmbGg3K3YzUjVlQkRvcWxr bVVENklaZzJNZzV6S0pzaTloCmxWZ1RYQlJ1Rm51Z1UwU3pPSEsrUk11UXJ6K1Q3M1UrZUxVYjB1SGs0WkpGV2Q2RFVabkpxaXl3cmZiVUpqNApqSTl5QnlqMUNRS0JnQ3ZSaGl1U1FyYVRoS0VWRDZyOUw3cEt0Z2xRZ1EwakphREFKRy9MMWo2U3VyQ1JEY2V3CmhtVmI0TFQzaTZMeXJjQWFpUE9qWWF2ekZlVkFQMGxNMTYzenVkT0JjcmR3SFBma2Z3LzhaUDV4Y3ppRWhDV1oKdVJGUDY5bFRGMFVWRWNkUFA2eXJra0JkT1YwMVpaL2dBVWpvRjkyeHk5aVk0ZWRQRExpNW92RTRCQW9HQkFNT0IKQ0ZqZGFlN01HUkpGZ2pjZzc2UisyYzJaRnhFWHJVaXdmeUZmY2s1WTYzUFJ1czdZckJCR09pcktVUWREN0V1aAp0L2pYYmZyMVBVa2pWenhpMzdDZ0NEekJ6bGRSeFFvbWw3M1dQWEF気持ちlkYkxBenpmOFMvWWsxVlpSR3laVVAKTVVhWHYraGs0Um5Gcm0xL0dFU1p5aGRtdGJyRDV1YlRQaGZGeWcyUkFvR0FhTHFWa1BHMTNaMDBiQlZ5VW5TS2oKSEh4Y1ByTEh6aXdHZEFvRVRPOWZNVnhWV3lEY0lXN3hYY08xbXlBUDJXSkpTaTV0ZHpxY3djeUVBcjk0ZmFDVgpnWDFXYmpxa2hqbDBUemtheUdyajBRY0p1elJyT0pQQ2dnYkFKckhva1B5S3ZSa2xHST9hNnBjNGs1SmIwYkZOCkFhdlJ1MFBId2hGSm1sY0xHZThlRURrPQotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tCg=="

@st.cache_resource
def get_ss_worksheet():
    # OPSCHOONACTIE: Verwijder alle spaties en enters uit de Base64 string voor het decoderen
    clean_b64 = re.sub(r'[^a-zA-Z0-9+/=]', '', B64_KEY)
    decoded_key = base64.b64decode(clean_b64).decode("utf-8")
    
    info = {
        "type": "service_account",
        "project_id": "dropping2026",
        "private_key": decoded_key,
        "client_email": "droping-final@dropping2026.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds).open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").worksheet("Data")

def get_db():
    try:
        ws = get_ss_worksheet()
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        # Als de database nog helemaal leeg is, maken we een lege tabel met de juiste headers
        return pd.DataFrame(columns=["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Timer", "Start_Lat", "Start_Lon"])

def save_to_db(df):
    ws = get_ss_worksheet()
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

# --- 2. AUTH & STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip()
    l_names = st.text_input("Leden")
    
    if st.button("Start Deelnemer"):
        if t_name == "THOMASBAAS":
            st.session_state.role = "admin"
            st.session_state.logged_in = True
            st.rerun()
        elif t_name and l_names:
            df = get_db()
            # Voeg team toe als het nog niet bestaat
            if t_name not in df['Teamnaam'].values:
                new_row = {
                    "Teamnaam": t_name, "Leden": l_names, 
                    "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", 
                    "Score": 0, "Timer": "00:00", 
                    "Start_Lat": 0.0, "Start_Lon": 0.0
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True).fillna(0)
                save_to_db(df)
            
            st.session_state.team = t_name
            st.session_state.role = "user"
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.warning("Vul aub beide velden in.")

else:
    # --- 3. ADMIN PANEL ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db()
        st.dataframe(df, use_container_width=True)
        
        if not df.empty:
            target = st.selectbox("Selecteer Team", df['Teamnaam'].unique())
            c1, c2, c3 = st.columns(3)
            with c1:
                msg = st.text_input("Push Opdracht")
                if st.button("Verstuur"):
                    df.loc[df['Teamnaam'] == target, 'Alarm'] = msg
                    save_to_db(df); st.success("Gepusht!")
            with c2:
                new_time = st.text_input("Timer (bijv. 45:00)")
                if st.button("Zet Tijd"):
                    df.loc[df['Teamnaam'] == target, 'Timer'] = new_time
                    save_to_db(df); st.success("Tijd aangepast!")
            with c3:
                new_pts = st.number_input("Score", value=0)
                if st.button("Zet Punten"):
                    df.loc[df['Teamnaam'] == target, 'Score'] = new_pts
                    save_to_db(df); st.success("Punten aangepast!")
        
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

    # --- 4. TEAM DASHBOARD ---
    else:
        # Refresh script (elke 10 sec)
        st.components.v1.html("<script>setTimeout(function(){window.location.reload();}, 10000);</script>", height=0)
        
        df = get_db()
        # Haal de rij van het huidige team op
        my_data = df[df['Teamnaam'] == st.session_state.team].iloc[0]

        # Check voor alarmen
        if str(my_data['Alarm']) != "GEEN":
            st.error(f"🚨 **NIEUWE OPDRACHT:** {my_data['Alarm']}")
            if st.button("Ik heb de opdracht begrepen"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                save_to_db(df); st.rerun()

        st.title(f"Team: {st.session_state.team}")
        col1, col2 = st.columns(2)
        col1.metric("Resterende Tijd", my_data['Timer'])
        col2.metric("Huidige Score", f"{my_data['Score']} Pnt")

        # Kaart logica
        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.info("Kies op de kaart waar jullie denken dat je gedropt bent.")
            m = folium.Map(location=[51.2194, 4.4025], zoom_start=10)
            st_data = st_folium(m, width=700, height=400)
            if st_data and st_data['last_clicked']:
                lat, lon = st_data['last_clicked']['lat'], st_data['last_clicked']['lng']
                if st.button("Bevestig Startpunt"):
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lat'] = lat
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lon'] = lon
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "DROPPING"
                    save_to_db(df); st.rerun()
        else:
            start = [my_data['Start_Lat'], my_data['Start_Lon']]
            finish = [51.2435, 4.4452]
            m = folium.Map(location=start, zoom_start=13)
            folium.Marker(start, tooltip="Jullie Start").add_to(m)
            folium.Marker(finish, tooltip="FINISH", icon=folium.Icon(color='red')).add_to(m)
            folium.PolyLine([start, finish], color="blue", dash_array='10').add_to(m)
            st_folium(m, width=700, height=500)

        if st.button("Uitloggen"): st.session_state.logged_in = False; st.rerun()
