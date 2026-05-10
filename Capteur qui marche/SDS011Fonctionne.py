import time
from sds011 import SDS011

# --- CONFIGURATION USB ---
PORT = "/dev/ttyUSB0"

try:
    sensor = SDS011(PORT, use_query_mode=True)
    print(f"Capteur connecté sur {PORT}")
except Exception as e:
    print(f"Erreur : Capteur non trouvé. Vérifie le branchement USB.")
    sensor = None

def mesurer():
    if sensor:
        sensor.sleep(sleep=False) # Allume le ventilateur
        print("Préchauffage 15s...")
        time.sleep(15)
        
        pm25, pm10 = sensor.query() # Mesure
        
        sensor.sleep(sleep=True) # Éteint
        return pm25, pm10
    return None, None

# Boucle infinie
if sensor:
    try:
        while True:
            p25, p10 = mesurer()
            print(f"[{time.strftime('%H:%M:%S')}] PM2.5: {p25} | PM10: {p10}")
            print("Attente 1 minute...")
            time.sleep(60)
    except KeyboardInterrupt:
        sensor.sleep(sleep=True)
        print("Arrêté.")