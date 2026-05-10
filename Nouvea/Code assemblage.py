import threading
import time
import smbus2
import serial
import mysql.connector
import RPi.GPIO as GPIO
from datetime import datetime

# --- CONFIGURATION BASE DE DONNÉES ---
DB_CONFIG = {
    'host': '192.168.101.150', # IP du serveur central
    'user': 'root',
    'password': 'admin',
    'database': 'metrologie'
}

def enregistrer_donnees(temp, pm25, etat_porte):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """
        INSERT INTO releves_environnement
        (date_heure, temperature, particules_fines, porte_ouverte)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (datetime.now(), temp, pm25, etat_porte))
        conn.commit()
        print("[BDD] Données enregistrées.")
    except mysql.connector.Error as err:
        print(f"[BDD] Erreur : {err}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# --- CONFIGURATION MATÉRIELLE ---
PIN_ILS = 17          # Capteur de porte
PIN_RELAIS = 23       # Ventilateur
PIN_LED_R = 22        # LED Rouge (Seul retour visuel)
PORT_SDS = '/dev/ttyUSB0' # Port USB du capteur de particules

# --- SETUP GPIO ---
GPIO.setmode(GPIO.BCM)
GPIO.setup([PIN_RELAIS, PIN_LED_R], GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(PIN_ILS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# --- VARIABLES GLOBALES ---
temp_globale = 0.0
pm25_globale = 0.0

# --- FONCTIONS CAPTEURS ---

def lire_dht20():
    """Lit la température sur le bus I2C (adresse 0x38)"""
    try:
        bus = smbus2.SMBus(1)
        bus.write_i2c_block_data(0x38, 0xAC, [0x33, 0x00])
        time.sleep(0.1)
        data = bus.read_i2c_block_data(0x38, 0x71, 7)
        t_raw = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5])
        return ((t_raw / 1048576.0) * 200) - 50
    except:
        return 20.0 # Valeur de secours si capteur débranché

def lire_sds011():
    """Lit les particules fines sur l'USB"""
    global pm25_globale
    try:
        ser = serial.Serial(PORT_SDS, baudrate=9600, timeout=1)
        while True:
            data = ser.read(10)
            if len(data) == 10 and data[0] == 0xAA:
                pm25_globale = (data[3] * 256 + data[2]) / 10.0
            time.sleep(2)
    except:
        print("SDS011 non trouvé sur /dev/ttyUSB0")

# --- TÂCHE 1 : SURVEILLANCE ET VENTILATION ---
def task_environnement():
    global temp_globale
    while True:
        temp_globale = lire_dht20()
        etat_porte = GPIO.input(PIN_ILS)
        print(f"[LOG] Temp: {temp_globale:.1f}°C | PM2.5: {pm25_globale} | Porte: {etat_porte}")

        # Gestion du ventilateur (Seuil 27°C)
        if temp_globale > 27.0:
            GPIO.output(PIN_RELAIS, GPIO.HIGH)
        else:
            GPIO.output(PIN_RELAIS, GPIO.LOW)

        # Envoi des données vers le serveur central
        enregistrer_donnees(temp_globale, pm25_globale, etat_porte)
        time.sleep(5)

# --- TÂCHE 2 : DIGICODE ET COMPARAISON ---
def task_digicode():
    while True:
        print("\nSaisissez le code d'accès :")
        code = input()
        
        if code == "1234":
            print("Accès OK - Porte déverrouillée")
            GPIO.output(PIN_LED_R, GPIO.HIGH) # LED fixe = Accès autorisé
            
            t1 = temp_globale
            print(f"Température avant : {t1}°C")
            
            # Attente ouverture puis fermeture
            while GPIO.input(PIN_ILS) == GPIO.LOW: time.sleep(0.1)
            print("Porte ouverte...")
            
            while GPIO.input(PIN_ILS) == GPIO.HIGH: time.sleep(0.1)
            print("Porte refermée.")
            
            t2 = temp_globale
            print(f"Température après : {t2}°C. Différence : {t2-t1:.2f}")
            
            GPIO.output(PIN_LED_R, GPIO.LOW)
        else:
            print("Code FAUX")
            # Clignotement rapide pour signaler l'erreur
            for _ in range(5):
                GPIO.output(PIN_LED_R, GPIO.HIGH)
                time.sleep(0.1)
                GPIO.output(PIN_LED_R, GPIO.LOW)
                time.sleep(0.1)

# --- LANCEMENT ---
if __name__ == "__main__":
    # Thread pour les particules (lecture continue)
    threading.Thread(target=lire_sds011, daemon=True).start()
    # Thread pour la clim
    threading.Thread(target=task_environnement, daemon=True).start()
    # Thread pour le digicode
    threading.Thread(target=task_digicode, daemon=True).start()
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        GPIO.cleanup()