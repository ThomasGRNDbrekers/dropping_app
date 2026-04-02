import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import st_folium
import time
import math

# --- 1. CONFIGURATIE ---
st.set_page_config(page_title="Dropping 2026", layout="wide")
FINISH_COORDS = [51.2435, 4.4452] # Bouckenborgh
START_PUNTEN = 1000.0
TIJD_DOEL_UUR = 5 
PUNTEN_PER_SEC = START_PUNTEN / (TIJD_DOEL_UUR * 3600)
REFRESH_RATE = 10 

# --- HELPERS ---
def haversine_distance(p1, p2):
    """Afstand tussen twee punten in km"""
    lat1, lon1 = p1
    lat2, lon2 = p2
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_distance_to_line(p_cur, p_start, p_fin):
    try:
        y3, x3 = p_cur
        y1, x1 = p_start
        y2, x2 = p_fin
        px, py = x2-x1, y2-y1
        norm = px*px + py*py
        if norm == 0: return 0
        u = max(0, min(1, ((x3-x1)*px + (y3-y1)*py) / float(norm)))
        dx, dy = (x1 + u*px) - x3, (y1 + u*py) - y3
        return math.sqrt(dx*dx + dy*dy) * 111
    except: return 0

@st.cache_resource
def get_ss_worksheet():
    try:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds).open_by_key("13KipcWXoXnf-ZRK_sughyft3qYOEoYlSf9XAj_dE9kI").sheet1
    except: return None

def get_db_as_df():
    ws = get_ss_worksheet()
    cols = ["Teamnaam", "Leden", "Fase", "Alarm", "Score", "Last_Update", "Start_Lat", "Start_Lon", "Cur_Lat", "Cur_Lon"]
    if not ws: return pd.DataFrame(columns=cols)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if df.empty or "Teamnaam" not in df.columns: return pd.DataFrame(columns=cols)
    for c in ['Score', 'Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon', 'Last_Update']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    return df

def save_df_to_db(df):
    ws = get_ss_worksheet()
    if ws and not df.empty: # Veiligheid: nooit een lege DF opslaan
        ws.update([df.columns.values.tolist()] + df.values.astype(str).tolist())

# --- LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📍 Dropping 2026")
    t_name = st.text_input("Teamnaam").strip().upper()
    t_pass = st.text_input("Wachtwoord (enkel voor Admin)", type="password")
    
    if st.button("Aanmelden"):
        if t_name == "THOMASBAAS" and t_pass == "bobodropping":
            st.session_state.role, st.session_state.logged_in = "admin", True
            st.rerun()
        elif t_name and t_name != "THOMASBAAS":
            df = get_db_as_df()
            if t_name not in df['Teamnaam'].astype(str).values:
                new_row = {"Teamnaam": t_name, "Leden": "", "Fase": "LOCATIE_KIEZEN", "Alarm": "GEEN", "Score": START_PUNTEN, "Last_Update": time.time(), "Start_Lat": 0.0, "Start_Lon": 0.0, "Cur_Lat": 0.0, "Cur_Lon": 0.0}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_df_to_db(df)
            st.session_state.team, st.session_state.role, st.session_state.logged_in = t_name, "user", True
            st.rerun()
else:
# --- 4. ADMIN PANEL (THOMASBAAS) ---
    if st.session_state.role == "admin":
        st.title("🕹️ Control Room - Master Overview")
        
        # Auto-refresh Admin elke 15 seconden (iets trager dan user om API te sparen)
        st.components.v1.html(f"<script>setTimeout(function(){{ window.location.reload(); }}, 15000);</script>", height=0)
        
        df = get_db_as_df()

        # --- LIVE KAART VOOR ADMIN ---
        st.subheader("📍 Live Locaties Teams")
        if not df.empty:
            # Centreer de kaart tussen de teams of op de finish
            m_admin = folium.Map(location=FINISH_COORDS, zoom_start=12)
            
            # Voeg Finish toe
            folium.Marker(FINISH_COORDS, tooltip="FINISH: Bouckenborgh", icon=folium.Icon(color='red', icon='flag')).add_to(m_admin)

            colors = ['blue', 'orange', 'green', 'purple', 'cadetblue'] # Verschillende kleuren voor teams
            
            for i, row in df.iterrows():
                t_name = row['Teamnaam']
                color = colors[i % len(colors)]
                
                # Als het team al gestart is (coördinaten zijn niet 0)
                if row['Cur_Lat'] != 0:
                    start_pos = [row['Start_Lat'], row['Start_Lon']]
                    curr_pos = [row['Cur_Lat'], row['Cur_Lon']]
                    
                    # 1. Teken de ideale lijn voor dit team
                    folium.PolyLine([start_pos, FINISH_COORDS], color=color, weight=2, opacity=0.5, dash_array='5', tooltip=f"Lijn {t_name}").add_to(m_admin)
                    
                    # 2. Teken hun huidige positie
                    folium.Marker(
                        curr_pos, 
                        tooltip=f"Team: {t_name}",
                        popup=f"<b>{t_name}</b><br>Score: {int(row['Score'])}<br>Status: {row['Fase']}",
                        icon=folium.Icon(color=color, icon='info-sign')
                    ).add_to(m_admin)
                    
                    # 3. Teken een cirkel rond hun positie
                    folium.Circle(curr_pos, radius=100, color=color, fill=True, opacity=0.2).add_to(m_admin)

            st_folium(m_admin, width="100%", height=500)
        else:
            st.info("Nog geen teams aangemeld.")

        st.divider()

        # --- CONTROLS (OPDRACHTEN & PUNTEN) ---
        st.subheader("🎮 Team Management")
        if not df.empty:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.dataframe(df[['Teamnaam', 'Score', 'Fase']])
            
            with col2:
                target = st.selectbox("Selecteer Team voor actie:", df['Teamnaam'].unique())
                msg = st.text_area("Opdracht tekst (bv. 'Zoek de verborgen code bij de eik')")
                pts = st.number_input("Te verdienen punten", value=50, step=10)
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🚀 Stuur Opdracht"):
                        df.loc[df['Teamnaam'] == target, 'Alarm'] = f"{pts}|{msg}"
                        save_df_to_db(df)
                        st.success(f"Opdracht gepusht naar {target}!")
                        st.rerun()
                with c2:
                    if st.button("✅ Keur Goed & Tel Bij"):
                        val = str(df.loc[df['Teamnaam'] == target, 'Alarm'].values[0])
                        bonus = float(val.split('|')[0]) if '|' in val else 0
                        df.loc[df['Teamnaam'] == target, 'Score'] += bonus
                        df.loc[df['Teamnaam'] == target, 'Alarm'] = "GEEN"
                        save_df_to_db(df)
                        st.success(f"Bonus van {bonus} ptn toegekend aan {target}!")
                        st.rerun()

        if st.button("Uitloggen Admin"):
            st.session_state.logged_in = False
            st.rerun()

    # --- USER ---
    else:
        # Auto-refresh Deelnemer
        st.components.v1.html(f"<script>setTimeout(function(){{ window.location.reload(); }}, {REFRESH_RATE * 1000});</script>", height=0)
        
        df = get_db_as_df()
        team_idx = df['Teamnaam'] == st.session_state.team
        if not team_idx.any(): st.session_state.logged_in = False; st.rerun()
        my_data = df[team_idx].iloc[0]

        # Berekeningen
        if my_data['Fase'] == "DROPPING":
            nu = time.time()
            dt = nu - float(my_data['Last_Update'])
            dist_to_line = get_distance_to_line([my_data['Cur_Lat'], my_data['Cur_Lon']], [my_data['Start_Lat'], my_data['Start_Lon']], FINISH_COORDS)
            
            # Afgelegde afstand vanaf start bepalen voor Blind Mode
            dist_from_start = haversine_distance([my_data['Start_Lat'], my_data['Start_Lon']], [my_data['Cur_Lat'], my_data['Cur_Lon']])
            
            # Pas punten aan als ze verder dan 500m zijn (0.5 km)
            if dist_from_start > 0.5:
                straf = 1 + (dist_to_line * 5)
            else:
                straf = 1 # Eerste 500m geen extra straf voor afwijking
                
            nieuwe_score = max(0, float(my_data['Score']) - (dt * PUNTEN_PER_SEC * straf))
            df.loc[team_idx, 'Score'] = nieuwe_score
            df.loc[team_idx, 'Last_Update'] = nu
            save_df_to_db(df)
            my_data['Score'] = nieuwe_score

        # UI
        st.subheader(f"Team: {st.session_state.team} | 🏆 {int(my_data['Score'])} pnt")
        
        # Alarm
        if "|" in str(my_data['Alarm']):
            pts, txt = str(my_data['Alarm']).split("|")
            st.error(f"🚨 OPDRACHT: {txt} (+{pts} ptn)")

        if my_data['Fase'] == "LOCATIE_KIEZEN":
            m = folium.Map(location=[51.2, 4.4], zoom_start=12)
            st_data = st_folium(m, width=700, height=400, key="start_map")
            if st_data and st_data.get("last_clicked"):
                if st.button("BEVESTIG STARTPUNT"):
                    clicked = st_data["last_clicked"]
                    df.loc[team_idx, ['Start_Lat', 'Start_Lon', 'Cur_Lat', 'Cur_Lon']] = [clicked['lat'], clicked['lng'], clicked['lat'], clicked['lng']]
                    df.loc[team_idx, 'Fase'] = "DROPPING"
                    df.loc[team_idx, 'Last_Update'] = time.time()
                    save_df_to_db(df); st.rerun()
        else:
            # KAART LOGICA
            start = [my_data['Start_Lat'], my_data['Start_Lon']]
            current = [my_data['Cur_Lat'], my_data['Cur_Lon']]
            dist_from_start = haversine_distance(start, current)
            
            # Bepaal of we in Blind Mode zitten
            is_blind = dist_from_start > 0.5
            
            if is_blind:
                st.warning("🙈 BLIND MODE ACTIEF: De kaart is verdwenen! Navigeer op de lijn.")
                # Gebruik een lege witte kaart (tiles=None)
                m = folium.Map(location=current, zoom_start=16, tiles=None)
                folium.TileLayer(tiles='http://localhost:8080/none', attr='Blind Mode').add_to(m) # Forceert lege achtergrond
            else:
                st.success(f"Nog {round(500 - (dist_from_start*1000))}m tot Blind Mode...")
                m = folium.Map(location=current, zoom_start=15)
            
            # Teken de ideale lijn en posities
            folium.PolyLine([start, FINISH_COORDS], color="green", weight=3, dash_array='10').add_to(m)
            folium.Marker(FINISH_COORDS, icon=folium.Icon(color='red', icon='flag')).add_to(m)
            folium.Marker(current, icon=folium.Icon(color='blue', icon='user')).add_to(m)
            folium.Circle(current, radius=30, color='blue', fill=True).add_to(m)
            
            st_folium(m, width=700, height=500)

        if st.button("Log uit"): st.session_state.logged_in = False; st.rerun()
