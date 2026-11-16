import os
import logging
import datetime
import requests

# Configurare jurnalizare
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Sursă meteo gratuită (Open-Meteo) fără cheie API - coordonate București
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
LATITUDE = "44.43"
LONGITUDE = "26.10"

def fetch_weather_forecast():
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": "windspeed_10m,shortwave_radiation",
        "timezone": "auto"
    }
    try:
        response = requests.get(WEATHER_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        winds = hourly.get("windspeed_10m", [])
        solars = hourly.get("shortwave_radiation", [])
        
        max_wind = max(winds) if winds else 0
        max_solar = max(solars) if solars else 0
        
        return {
            "max_wind": max_wind,
            "max_solar": max_solar,
            "count": len(times)
        }
    except Exception as e:
        logging.error(f"Erore meteo: {e}")
        return None

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.error("Secretele Telegram lipsesc!")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        logging.info("Mesaj trimis pe Telegram cu succes!")
        return True
    except Exception as e:
        logging.error(f"Erore trimitere Telegram: {e}")
        return False

def main():
    logging.info("Pornire procesare alerte energie...")
    weather = fetch_weather_forecast()
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if weather:
        msg = (
            f"⚡ *Raport Automat Energie & Meteo* ⚡\n"
            f"📅 Data/Ora: `{now}`\n\n"
            f"🌤️ *Prognoză Open-Meteo (24h):*\n"
            f"• Vânt max: `{weather['max_wind']} km/h`\n"
            f"• Radiație solară max: `{weather['max_solar']} W/m²`\n\n"
            f"✅ *Status sistem:* GitHub Actions funcționează perfect!"
        )
    else:
        msg = f"⚠️ *Alertă:* Nu s-au putut prelua datele meteo la `{now}`."
        
    send_telegram_alert(msg)

if __name__ == "__main__":
    main()
