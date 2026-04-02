import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt
import datetime

# --- CONFIG ---
FINISH = (51.2453, 4.4534)  # JC Bouckenborgh

# Koppeling met Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)


def get_data():
    return conn.read(worksheet="Data", ttl=0)


def update_team(team_name, lat, lon, score, fase, alarm):
    # In een echte app schrijf je hier naar de sheet.
    # Voor nu simuleren we de dataflow.
    df = pd.DataFrame([{
        "Teamnaam": team_name, "Lat": lat, "Lon": lon,
        "Score": score, "Fase": fase, "Alarm": alarm,
        "Update": datetime.datetime.now().strftime("%H:%M:%S")
    }])
    # In Streamlit Cloud configureer je de secrets voor schrijf-toegang.
    return df


# --- AUTH ---
if 'auth' not in st.session_state:
    st.session_state.auth = None

# --- UI ---
st.set_page_config(page_title="RECHTDOOR 2026", layout="wide")

if st.session_state.auth is None:
    st.title("🔐 Project: RECHTDOOR!")
    tab1, tab2 = st.tabs(["Vrijwilligers", "Control Room"])

    with tab1:
        t_name = st.text_input("Teamnaam")
        if st.button("Start als Team"):
            st.session_state.auth = "TEAM"
            st.session_state.teamname = t_name
            st.rerun()

    with tab2:
        u = st.text_input("Admin User")
        p = st.text_input("Wachtwoord", type="password")
        if st.button("Login Baas"):
            if u == "THOMASBAAS" and p == "DROPPING2026":
                st.session_state.auth = "ADMIN"
                st.rerun()
            else:
                st.error("Toegang geweigerd.")

# --- ADMIN SECTIE ---
elif st.session_state.auth == "ADMIN":
    st.title("🛰️ MISSION CONTROL: THOMASBAAS")

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📢 Alarm Paneel")
        alarm_msg = st.selectbox("Activeer Alarm", ["GEEN", "GET BACK", "GET UP", "PHOTO PYRAMID", "STRANGER DANGER"])
        if st.button("PUSH ALARM"):
            st.success(f"Alarm {alarm_msg} verzonden!")

        st.divider()
        st.subheader("📈 Team Overzicht")
        # Hier zou je de tabel uit Google Sheets tonen
        st.write("Team A: 92% | Team B: 78%")

    with col2:
        m = folium.Map(location=[51.3, 4.45], zoom_start=11, tiles="CartoDB dark_matter")
        folium.Marker(FINISH, tooltip="FINISH: Bouckenborgh", icon=folium.Icon(color='blue')).add_to(m)
        st_folium(m, width=700, height=500)

# --- TEAM SECTIE ---
elif st.session_state.auth == "TEAM":
    st.title(f"🚩 Team: {st.session_state.teamname}")

    # Gebruik de browser locatie (of slider voor demo)
    lat = st.sidebar.slider("Simuleer Lat", 51.2, 51.4, 51.3789, format="%.4f")
    lon = st.sidebar.slider("Simuleer Lon", 4.3, 4.8, 4.4715, format="%.4f")

    # FASE LOGICA
    if 'phase' not in st.session_state:
        st.session_state.phase = "GUESS"

    if st.session_state.phase == "GUESS":
        st.info("Waar ben je? Duid aan op de kaart.")
        m = folium.Map(location=[lat, lon], zoom_start=15)
        folium.ClickForMarker().add_to(m)
        st_folium(m, height=300)
        if st.button("Bevestig Locatie"):
            st.session_state.phase = "MOVE"
            st.session_state.startpoint = (lat, lon)
            st.rerun()

    else:
        st.metric("Score", "100%")
        # ALARM CHECK (Zou uit de Sheet komen)
        st.warning("🚨 OPDRACHT: GET UP! Klim ergens op en maak een foto.")
        st.file_uploader("Upload bewijs")

        m = folium.Map(location=[lat, lon], zoom_start=14)
        folium.PolyLine([st.session_state.startpoint, FINISH], color="green", weight=5).add_to(m)
        folium.Marker([lat, lon], icon=folium.Icon(color='red')).add_to(m)
        st_folium(m, height=400)

if st.sidebar.button("Logout"):
    st.session_state.auth = None
    st.rerun()