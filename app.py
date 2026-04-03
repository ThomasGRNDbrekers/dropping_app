from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
import json

app = FastAPI()
DB = "dropping.db"

# --- DATABASE SETUP ---
def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS teams 
            (name TEXT PRIMARY KEY, lat REAL, lon REAL, score INTEGER)""")
init_db()

# --- API ENDPOINTS ---
class LocationUpdate(BaseModel):
    name: str
    lat: float
    lon: float

@app.post("/update")
async def update(data: LocationUpdate):
    with sqlite3.connect(DB) as conn:
        conn.execute("INSERT OR REPLACE INTO teams (name, lat, lon, score) VALUES (?, ?, ?, 1000)",
                     (data.name.upper(), data.lat, data.lon))
    return {"status": "success"}

@app.get("/teams")
async def get_teams():
    with sqlite3.connect(DB) as conn:
        cursor = conn.execute("SELECT name, lat, lon FROM teams")
        return [{"name": r[0], "lat": r[1], "lon": r[2]} for r in cursor.fetchall()]

# --- FRONTEND (HTML + JS) ---
@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dropping 2026</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>
            body { font-family: sans-serif; margin: 0; padding: 20px; text-align: center; }
            #map { height: 300px; width: 100%; border-radius: 10px; margin-top: 20px; }
            button { background: #007bff; color: white; border: none; padding: 15px; border-radius: 5px; font-size: 16px; cursor: pointer; }
            input { padding: 10px; margin: 10px; border: 1px solid #ccc; width: 80%; }
            .admin-section { display: none; margin-top: 30px; border-top: 2px solid #eee; }
        </style>
    </head>
    <body>
        <h1>🏃 Dropping 2026</h1>
        
        <input type="text" id="teamName" placeholder="Teamnaam invullen...">
        <br>
        <button onclick="sendLocation()">📍 Deel mijn Locatie</button>
        <p id="status"></p>

        <div id="map"></div>

        <button onclick="document.getElementById('admin').style.display='block'" style="background:gray; margin-top:50px; font-size:10px;">Admin Overzicht</button>
        
        <div id="admin" class="admin-section">
            <h2>🛡️ Live Team Monitor</h2>
            <button onclick="refreshAdminMap()">Ververs Kaart</button>
        </div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var map = L.map('map').setView([51.2194, 4.4025], 13);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
            var marker;

            async function sendLocation() {
                const name = document.getElementById('teamName').value;
                if (!name) return alert("Vul eerst een teamnaam in!");

                if (!navigator.geolocation) return alert("GPS niet ondersteund");

                navigator.geolocation.getCurrentPosition(async (pos) => {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;

                    if (marker) map.removeLayer(marker);
                    marker = L.marker([lat, lon]).addTo(map).bindPopup("Jouw Locatie").openPopup();
                    map.setView([lat, lon], 15);

                    const res = await fetch('/update', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({name: name, lat: lat, lon: lon})
                    });
                    
                    if (res.ok) document.getElementById('status').innerText = "Locatie verzonden om " + new Date().toLocaleTimeString();
                }, (err) => {
                    alert("GPS Fout: " + err.message);
                }, { enableHighAccuracy: true });
            }

            async function refreshAdminMap() {
                const res = await fetch('/teams');
                const teams = await res.json();
                teams.forEach(t => {
                    L.marker([t.lat, t.lon]).addTo(map).bindPopup("Team: " + t.name);
                });
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
