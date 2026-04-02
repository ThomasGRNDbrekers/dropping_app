import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium

# --- CONFIG ---
st.set_page_config(page_title="Dropping 2026", layout="wide")
FINISH_COORDS = [51.2435, 4.4452]

@st.cache_resource
def get_ss_worksheet():
    # Haal de JSON-gegevens rechtstreeks uit de Streamlit Secrets
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(
        info, 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
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
            df = get_db()
            if t_name not in df['Teamnaam'].values:
                new = {"Teamnaam": t_name, "Leden": l_names, "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": 0, "Timer": "01:00:00", "Start_Lat": 0.0, "Start_Lon": 0.0}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True).fillna(0)
                save_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
else:
    # --- ADMIN ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room")
        df = get_db()
        st.dataframe(df, use_container_width=True)
        
        if not df.empty:
            target = st.selectbox("Selecteer Team", df['Teamnaam'].unique())
            c1, c2, c3 = st.columns(3)
            with c1:
                preset = st.selectbox("Opdracht:", ["Eigen tekst...", "🚨 BACK ON TRACK!", "📸 FOTO OPDRACHT", "🧩 RAADSEL"])
                custom = st.text_input("Of typ zelf:")
                msg = custom if custom else preset
                if st.button("Push naar Team"):
                    df.loc[df['Teamnaam'] == target, 'Alarm'] = msg
                    save_to_db(df); st.success("Verzonden!")
            with c2:
                new_t = st.text_input("Nieuwe Tijd (HH:MM:SS)")
                if st.button("Update Klok"):
                    df.loc[df['Teamnaam'] == target, 'Timer'] = new_t
                    save_to_db(df); st.success("Tijd aangepast!")
            with c3:
                new_s = st.number_input("Punten", value=0)
                if st.button("Update Punten"):
                    df.loc[df['Teamnaam'] == target, 'Score'] = new_s
                    save_to_db(df); st.success("Score aangepast!")
        
        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()

    # --- DEELNEMER ---
    else:
        st.components.v1.html("<script>setTimeout(function(){window.location.reload();}, 15000);</script>", height=0)
        df = get_db()
        my_data = df[df['Teamnaam'] == st.session_state.team].iloc[0]

        if str(my_data['Alarm']) != "GEEN":
            st.error(f"🚨 **OPDRACHT:** {my_data['Alarm']}")
            if st.button("Gelezen"):
                df.loc[df['Teamnaam'] == st.session_state.team, 'Alarm'] = "GEEN"
                save_to_db(df); st.rerun()
            st.stop()

        st.title(f"Team: {st.session_state.team}")
        c1, c2 = st.columns(2)
        c1.metric("Tijd over", my_data['Timer'])
        c2.metric("Score", f"{my_data['Score']} Pnt")

        if my_data['Fase'] == "LOCATIE_KIEZEN":
            st.info("Waar zijn jullie gedropt?")
            m = folium.Map(location=[51.2, 4.4], zoom_start=11)
            st_data = st_folium(m, width="100%", height=400)
            if st_data and st_data['last_clicked']:
                lat, lon = st_data['last_clicked']['lat'], st_data['last_clicked']['lng']
                if st.button("Bevestig Startlocatie"):
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lat'] = lat
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Start_Lon'] = lon
                    df.loc[df['Teamnaam'] == st.session_state.team, 'Fase'] = "DROPPING"
                    save_to_db(df); st.rerun()
        else:
            start = [my_data['Start_Lat'], my_data['Start_Lon']]
            m = folium.Map(location=start, zoom_start=14)
            folium.Marker(start, tooltip="Start").add_to(m)
            folium.Marker(FINISH_COORDS, tooltip="Finish", icon=folium.Icon(color='red')).add_to(m)
            folium.PolyLine([start, FINISH_COORDS], color="blue", dash_array='10').add_to(m)
            st_folium(m, width="100%", height=500)

        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()
