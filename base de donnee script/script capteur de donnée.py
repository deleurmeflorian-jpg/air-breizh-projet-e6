import time
import smbus2
import RPi.GPIO as GPIO

# --- CONFIGURATION ---
I2C_BUS = 1  # Bus I2C standard sur RPi
DHT20_ADDR = 0x38 # Adresse I2C du DHT20
PIN_RELAIS = 23   # GPIO connecté au relais du ventilateur
SEUIL_TEMP_MAX = 27.0 # Seuil d'activation en °C (Cahier des charges)

# --- INIT GPIO ---
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_RELAIS, GPIO.OUT)
GPIO.output(PIN_RELAIS, GPIO.LOW) # Ventilateur éteint par défaut

def lire_dht20():
    """Lit la température et l'humidité du capteur I2C DHT20"""
    bus = smbus2.SMBus(I2C_BUS)
    
    # Commande pour lancer la mesure
    bus.write_i2c_block_data(DHT20_ADDR, 0xAC, [0x33, 0x00])
    time.sleep(0.1) # Attendre la conversion (80ms min)
    
    # Lecture des 7 octets de données
    data = bus.read_i2c_block_data(DHT20_ADDR, 0x71, 7)
    
    # Calculs selon la datasheet DHT20
    h_raw = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4))
    t_raw = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5])
    
    humidite = (h_raw / 1048576.0) * 100
    temperature = ((t_raw / 1048576.0) * 200) - 50
    
    bus.close()
    return temperature, humidite

try:
    print("Contrôle Climatique Démarré...")
    while True:
        try:
            temp, hum = lire_dht20()
            print(f"Temp: {temp:.2f}°C | Hum: {hum:.2f}%")

            # --- Logique d'asservissement (Hystérésis simple) ---
            if temp > SEUIL_TEMP_MAX:
                GPIO.output(PIN_RELAIS, GPIO.HIGH)
                print("-> ALERTE : Ventilation ACTIVÉE")
            elif temp < (SEUIL_TEMP_MAX - 2.0): # On éteint si on descend 2°C sous le seuil
                GPIO.output(PIN_RELAIS, GPIO.LOW)
                print("-> Normal : Ventilation ÉTEINTE")
                
        except Exception as e:
            print(f"Erreur lecture capteur : {e}")
            
        time.sleep(5)

except KeyboardInterrupt:
    GPIO.cleanup()
    print("Arrêt.")