import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, asin, sqrt

# --- DE FINITIEVE FIX VOOR DE VERBINDING ---
# We maken een dictionary met EXACT de namen die de Google API verwacht
creds = {
    "type": "service_account",
    "project_id": "dropping2026",
    "private_key_id": "ff7a191a74fb7123d318f50728b527dcfc09bcc9",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDFPr2jz214sdnZ\naOYDhviCBsAmny1/iZhwEe45+uw25953vRSpUXf5fsLF6OHtZSxNR+IGqANRp0BV\nqgrK7X/ytpFQitfMelMDnKrKfnGqhOpJPGrO52z8+OpKGOQPXMSZmjRd79US3cjB\nm24C8igLh3tLuFL0LbGG/GPN2LpBQ8/7zAp1Xo6x82gMrGCy1PEEQyqm/YrKOBCk\nnJDBPz/CDIvDSzIIXOrwnz9x/P5eqvynFJrO5v9Kye+xH7Os14BtG7Q24GF92GG4\n2FR4F2FCHb5nH6msLCdUX3iYC+6mTmJnPpVEqnQqSmILfuw/+20t9K887nSxiPmh\n0PSdr30tAgMBAAECggEAD//rSfd4Ybm1hONI2IDmisTplHMa3Eqo7PBQvW8bTEc0\niSHIjwUpgPlqwGXdYRBw+UeAhWSJY7fNf2q8FjgRMKWQCzM+rDAWU0eY+rTVMLfi\n5ElsauJOuYTRxmxsoCAONN0owcpDo6njZWxfo7QJEl8Cne1dUerHSNPoyZ4QBQf1\nSFjMs2TZYl16DtwuQmmQ4PYvodaBhqtVGZjFaizGHu3BXjZT2kTojGakQz9qQd+l\nrJSo8iJG+4xt4htt8QQys6AK6t9JSWIVnbfScM79dJY3CqlV/0QAQ2tz7TGlGguN\vmlyWMyyTiH6l+ypLSYMe8TPQSaiaVUQ1/i9SgHrEQKBgQD3gib6kKYLSr1stsVx\nqNMsQiXircrDnZB9bQc/y0zVHBmRl30cOttAhk5ibCozbMgCT1Rz+vi7DEmquR57\ncdLDB8dbtBoOJzeGB7pexqkOXifRwFzipJLvfrQ7y+VPk2kC0TIYsDdAF2syAKaH\YYQVXfeXIx9axwBYrhsKFHnSUQKBgQDMAyEnNSJrIWArf8k9bqMDG0ml7JU6GxKQ\nbneLHITFkpWd9VsDjRPdAQrRJEHfLSvEXHpUHLo7kYWU9S49KkQAgV9Y53mBZS13\nCSkoBYfA3MsUZdxeXcTxL5n0/HSmzTswZzZPOrjCZOxvh0Fmm5dQ6z4jsC06B5Sr\n1VkyHJOKHQKBgQCGTOgro9uFWwvH9rDSSKI1bLsz8cuJM3EYrdV2JzFMnc+98W5g\nqAsaSwYzX6/ScZ9hqXwQ5siabkN20LYak5uiWhEx0Fsm/N6i6oSVMsS+2BZROUjt\nbhGQxLa1j6Cg+kLL1YmSXePM8ignXLT/1skd8vwK1XMJBdxJQkfHw26K0QKBgAYy\piQxygzlI63OoQd7v/oNLyyaRmJQhjzbDkisoh/6dw8ocA5oj8zsBi8aYeHs1mKN\nyK2bfdDnd95xoGj9SrmVNJdX2Ookb8ApCBYOLPSgAI9rFMnNIXmOT6gQr16N55lt\n2UmI6CoHtOMigcsjOPKdYvLknEsiBdM+lQofsh/FAoGBAKfZniAjAVKSqUJ8ivqu\n8qAnnIE6af3T2i7zHmyJPuj6fMlUPuQyuUhjOosxstHFrlDYUP2uuVbQhGxU4Pve\nw1ApbCpYLI6kF2b1M6xGKvT4iIdSWjtIZThoYrDUGITIqtiFUFox+9DICfX8h90z\n8LrBdsW6x75evTZx5kdH/pax\n-----END PRIVATE KEY-----\n",
    "client_email": "dropping2026@dropping2026.iam.gserviceaccount.com",
    "token_uri": "https://oauth2.googleapis.com/token",
}

# We gebruiken de standaard connection MAAR we overschrijven de credentials handmatig
conn = st.connection("gsheets", type=GSheetsConnection)
conn._instance.client.spreadsheet_service._credentials = conn._instance.client.spreadsheet_service._credentials.__class__.from_service_account_info(creds)

# De URL van je spreadsheet (mag ook in Secrets staan, maar voor de zekerheid hier)
SHEET_URL = "https://docs.google.com/spreadsheets/d/13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI/edit?usp=sharing"

# --- HULPFUNCTIES ---
def get_db():
    return conn.read(spreadsheet=SHEET_URL, worksheet="Data", ttl=1)
# --- 1. CONFIGURATIE ---
FINISH = (51.2453, 4.4534) # JC Bouckenborgh Antwerpen

st.set_page_config(page_title="RECHTDOOR 2026", layout="wide", initial_sidebar_state="expanded")

# Verbinding met Google Sheets via de Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. HULPFUNCTIES ---
def get_db():
    # ttl=1 zorgt dat de data elke seconde ververst wordt (belangrijk voor alarmen!)
    return conn.read(worksheet="Data", ttl=1)

def haversine(p1, p2):
    R = 6371000
    phi1, phi2 = radians(p1[0]), radians(p2[0])
    dphi, dlambda = radians(p2[0] - p1[0]), radians(p2[1] - p1[1])
    a = sin(dphi / 2)**2 + cos(phi1) * cos(phi2) * sin(dlambda / 2)**2
    return 2 * R * asin(sqrt(a))

# --- 3. LOGIN STATUS ---
if 'auth' not in st.session_state:
    st.session_state.auth = None

# --- 4. LOGIN SCHERM ---
if st.session_state.auth is None:
    st.title("📏 Project: RECHTDOOR 2026")
    role = st.radio("Wie ben je?", ["Vrijwilliger Team", "Control Room"])
    
    if role == "Control Room":
        u = st.text_input("Gebruikersnaam")
        p = st.text_input("Wachtwoord", type="password")
        if st.button("Login als Baas"):
            if u == "THOMASBAAS" and p == "DROPPING2026":
                st.session_state.auth = "ADMIN"
                st.rerun()
            else:
                st.error("Fout wachtwoord!")
    else:
        t_name = st.text_input("Teamnaam (exact zoals eerder ingevuld bij refresh)")
        if st.button("Start Missie"):
            if t_name:
                st.session_state.auth = "TEAM"
                st.session_state.teamname = t_name
                st.rerun()

# --- 5. INTERFACE: CONTROL ROOM (ADMIN) ---
elif st.session_state.auth == "ADMIN":
    st.title("🛰️ MISSION CONTROL - Baas Modus")
    df = get_db()
    
    if df.empty:
        st.warning("Nog geen teams aangemeld in de Google Sheet.")
    else:
        col_list, col_map = st.columns([1, 2])
        
        with col_list:
            st.subheader("📢 Teams & Alarmen")
            st.dataframe(df[["Teamnaam", "Fase", "Alarm"]])
            
            target_team = st.selectbox("Selecteer Team", df["Teamnaam"].unique())
            new_alarm = st.selectbox("Opdracht versturen", ["GEEN", "GET BACK", "GET UP", "PHOTO PYRAMID", "STRANGER DANGER"])
            
            if st.button("PUSH ALARM"):
                # Update de lokale dataframe en schrijf naar Google Sheets
                df.loc[df["Teamnaam"] == target_team, "Alarm"] = new_alarm
                conn.update(worksheet="Data", data=df)
                st.success(f"Alarm '{new_alarm}' verzonden naar {target_team}!")

        with col_map:
            st.subheader("Live Locaties")
            m_admin = folium.Map(location=[51.3, 4.45], zoom_start=11, tiles="CartoDB dark_matter")
            folium.Marker(FINISH, popup="FINISH", icon=folium.Icon(color='gold', icon='trophy', prefix='fa')).add_to(m_admin)
            
            # Toon alle teams op de kaart (als ze coördinaten hebben)
            for _, row in df.iterrows():
                if pd.notnull(row['Huidige_Lat']):
                    folium.Marker(
                        [row['Huidige_Lat'], row['Huidige_Lon']], 
                        popup=f"{row['Teamnaam']} ({row['Alarm']})",
                        icon=folium.Icon(color='red' if row['Alarm'] != "GEEN" else 'blue')
                    ).add_to(m_admin)
            st_folium(m_admin, width=700, height=500)

# --- 6. INTERFACE: VRIJWILLIGER (TEAM) ---
elif st.session_state.auth == "TEAM":
    df = get_db()
    
    # Check of team al bestaat in de Sheet, anders toevoegen
    if st.session_state.teamname not in df["Teamnaam"].values:
        new_row = pd.DataFrame([{"Teamnaam": st.session_state.teamname, "Alarm": "GEEN", "Fase": "GUESS", "Score": 100}])
        df = pd.concat([df, new_row], ignore_index=True)
        conn.update(worksheet="Data", data=df)
        st.rerun()

    # Haal specifieke data voor dit team op
    my_row = df[df["Teamnaam"] == st.session_state.teamname].iloc[0]
    
    st.title(f"🚩 Team: {st.session_state.teamname}")

    # GPS SIMULATIE (Omdat we geen echte native app hebben, vullen ze hier hun locatie in of via browser)
    st.sidebar.subheader("📍 Jouw Locatie")
    curr_lat = st.sidebar.number_input("Huidige Lat", value=float(my_row['Huidige_Lat']) if pd.notnull(my_row['Huidige_Lat']) else 51.3789, format="%.5f")
    curr_lon = st.sidebar.number_input("Huidige Lon", value=float(my_row['Huidige_Lon']) if pd.notnull(my_row['Huidige_Lon']) else 4.4715, format="%.5f")
    
    # Update locatie in DB bij elke verandering
    if curr_lat != my_row['Huidige_Lat'] or curr_lon != my_row['Huidige_Lon']:
        df.loc[df["Teamnaam"] == st.session_state.teamname, ["Huidige_Lat", "Huidige_Lon"]] = [curr_lat, curr_lon]
        conn.update(worksheet="Data", data=df)

    # ALARM DISPLAY
    if my_row["Alarm"] != "GEEN":
        st.error(f"⚠️ **OPDRACHT VAN DE BAAS:** {my_row['Alarm']}")
        st.audio("https://www.soundjay.com/buttons/beep-01a.mp3") # Optioneel geluidje
        st.file_uploader("Upload bewijs (foto)")
        if st.button("Opdracht Voltooid ✅"):
            df.loc[df["Teamnaam"] == st.session_state.teamname, "Alarm"] = "GEEN"
            conn.update(worksheet="Data", data=df)
            st.rerun()

    # FASE LOGICA
    if my_row["Fase"] == "GUESS":
        st.header("🔎 Waar ben je?")
        st.info("Kijk rond en duid op de kaart aan waar je denkt dat je bent.")
        m_guess = folium.Map(location=[curr_lat, curr_lon], zoom_start=15)
        folium.ClickForMarker(popup="Startpunt").add_to(m_guess)
        st_folium(m_guess, height=400)
        
        if st.button("Bevestig Startlocatie"):
            df.loc[df["Teamnaam"] == st.session_state.teamname, ["Start_Lat", "Start_Lon", "Fase"]] = [curr_lat, curr_lon, "MOVE"]
            conn.update(worksheet="Data", data=df)
            st.rerun()

    else:
        # Check afstand tot start (voor de 500m grens)
        start_pt = (my_row["Start_Lat"], my_row["Start_Lon"])
        dist_moved = haversine((curr_lat, curr_lon), start_pt)
        
        if dist_moved < 500:
            st.warning(f"Wandel nog {int(500 - dist_moved)} meter om de Ideale Lijn te activeren!")
        else:
            st.success("🎯 IDEALE LIJN GEACTIVEERD")
            m_live = folium.Map(location=[curr_lat, curr_lon], zoom_start=14)
            folium.PolyLine([start_pt, FINISH], color="green", weight=5, opacity=0.7).add_to(m_live)
            folium.Marker([curr_lat, curr_lon], icon=folium.Icon(color='red')).add_to(m_live)
            st_folium(m_live, height=400)

if st.sidebar.button("Uitloggen"):
    st.session_state.auth = None
    st.rerun()
