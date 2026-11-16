import requests
import datetime
import csv
import os
import logging

# Configurare jurnalizare (logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Preluare automată a secretelor configurate în GitHub Actions (sau din mediul local)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Endpoint-uri API (Înlocuiește cu API-ul tău meteo și furnizorul de date OPCOM/PZU)
WEATHER_API_URL = "https://api.example-weather.v1/forecast"
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "INTRODU_CHEIE_API_METEO_AICI")
OPCOM_API_URL = "https://api.example-opcom.v1/pzu/prices"

# Praguri de risc
WIND_RISK_THRESHOLD_MS = 12.0      # m/s
SOLAR_RISK_THRESHOLD_W_M2 = 800.0  # W/m²
PRICE_LOW_THRESHOLD_LEI = 50.0     # lei/MWh

CSV_FILENAME = "istoric_piata_energie.csv"
# ------------------------------

def fetch_weather_forecast():
    headers = {"Authorization": f"Bearer {WEATHER_API_KEY}"}
    params = {"country": "RO", "hours": 24}
    try:
        response = requests.get(WEATHER_API_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erore la interogarea API-ului meteo: {e}")
        return None

def fetch_opcom_pzu_prices():
    """
    Interoghează API-ul OPCOM și gestionează erorile de conexiune/răspuns.
    Trimite o alertă separată pe Telegram dacă serviciul este picat.
    """
    try:
        response = requests.get(OPCOM_API_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        error_msg = f"❌ *ERORE CRITICĂ API OPCOM (HTTP)*: {http_err}"
        logging.error(error_msg)
        send_telegram_alert(error_msg)
        return None
    except requests.exceptions.ConnectionError:
        error_msg = f"❌ *ERORE CONEXIUNE*: Nu se poate stabili conexiunea cu serverul OPCOM."
        logging.error(error_msg)
        send_telegram_alert(error_msg)
        return None
    except requests.exceptions.Timeout:
        error_msg = f"⚠️ *TIMEOUT API OPCOM*: Serviciul a răspuns prea lent."
        logging.error(error_msg)
        send_telegram_alert(error_msg)
        return None
    except Exception as e:
        error_msg = f"❌ *ERORE NEPREVĂZUTĂ OPCOM*: {e}"
        logging.error(error_msg)
        send_telegram_alert(error_msg)
        return None

def save_to_csv(data_row):
    file_exists = os.path.isfile(CSV_FILENAME)
    fields = [
        "timestamp", "hour", "wind_speed", "solar_rad", 
        "opcom_price", "alert_triggered", "alert_type"
    ]
    try:
        with open(CSV_FILENAME, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if not file_exists:
                writer.writeheader()
            writer.writerow(data_row)
    except Exception as e:
        logging.error(f"Erore la scrierea în fișierul CSV: {e}")

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Tokenul sau Chat ID-ul de Telegram nu sunt setate în variabilele de mediu. Mesaj: " + message)
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Erore de rețea la trimiterea alertei Telegram: {e}")

def analyze_market_with_safety():
    logging.info("Se inițiază interogarea fluxurilor de date...")
    
    weather_data = fetch_weather_forecast()
    opcom_prices = fetch_opcom_pzu_prices()
    
    # Dacă API-ul OPCOM nu răspunde, oprim execuția pentru a evita date corupte
    if not opcom_prices:
        logging.warning("Analiza a fost oprită din cauza lipsei datelor de la OPCOM.")
        return

    if not weather_data:
        logging.warning("Nu s-au putut obține datele meteo.")
        return

    forecast_intervals = weather_data.get('forecast', [])
    prices_by_hour = opcom_prices.get('prices', {})
    current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for interval in forecast_intervals:
        hour = interval.get('hour')
        wind_speed = interval.get('wind_speed', 0.0)
        solar_rad = interval.get('solar_rad', 0.0)
        current_price = prices_by_hour.get(str(hour), 200.0)
        
        alert_triggered = False
        alert_type = "NONE"
        
        if wind_speed >= WIND_RISK_THRESHOLD_MS and current_price <= PRICE_LOW_THRESHOLD_LEI:
            alert_triggered = True
            alert_type = "HIGH_WIND_LOW_PRICE"
            msg = f"🚨 *ALERTĂ CORELATĂ - SURPLUS EOLIAN*\n• Ora: {hour}:00 | Vânt: *{wind_speed} m/s* | Preț: *{current_price} lei/MWh*"
            send_telegram_alert(msg)
            
        elif solar_rad >= SOLAR_RISK_THRESHOLD_W_M2 and current_price <= PRICE_LOW_THRESHOLD_LEI:
            alert_triggered = True
            alert_type = "HIGH_SOLAR_LOW_PRICE"
            msg = f"☀️ *ALERTĂ CORELATĂ - VÂRF SOLAR*\n• Ora: {hour}:00 | Radiație: *{solar_rad} W/m²* | Preț: *{current_price} lei/MWh*"
            send_telegram_alert(msg)
            
        row_data = {
            "timestamp": current_timestamp,
            "hour": hour,
            "wind_speed": wind_speed,
            "solar_rad": solar_rad,
            "opcom_price": current_price,
            "alert_triggered": alert_triggered,
            "alert_type": alert_type
        }
        save_to_csv(row_data)
        
    logging.info("Ciclu de monitorizare finalizat cu succes.")

if __name__ == "__main__":
    analyze_market_with_safety
