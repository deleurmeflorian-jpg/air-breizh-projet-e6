import time
import adafruit_dht
import board
import RPi.GPIO as GPIO

# --- CONFIGURATION ---
# Pin physique 7 = GPIO 4
PIN_DHT = board.D4 
PIN_RELAIS = 23
SEUIL_TEMP_MAX = 27.0

# Initialisation du DHT22
# On force l'utilisation de libgpiod en interne pour éviter l'erreur "line 4"
dht_device = adafruit_dht.DHT22(PIN_DHT, use_pulseio=False)

# Initialisation du Relais
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_RELAIS, GPIO.OUT)
GPIO.output(PIN_RELAIS, GPIO.LOW)

print("--- Système de Contrôle DHT22 Activé ---")

try:
    while True:
        try:
            # Lecture des données
            temperature = dht_device.temperature
            humidite = dht_device.humidity

            if temperature is not None:
                print(f"Temp: {temperature:.1f}C | Hum: {humidite:.1f}%")
                
                # Logique du ventilateur
                if temperature > SEUIL_TEMP_MAX:
                    GPIO.output(PIN_RELAIS, GPIO.HIGH)
                    print(">> VENTILATEUR ALLUMÉ")
                else:
                    GPIO.output(PIN_RELAIS, GPIO.LOW)
                    print(">> VENTILATEUR ÉTEINT")

        except RuntimeError as error:
            # Les erreurs de lecture sont normales avec le DHT22
            # On ne fait rien et on laisse le programme continuer
            pass
        except Exception as e:
            print(f"Erreur inattendue : {e}")
            
        time.sleep(2.0) # Le DHT22 a besoin de 2 secondes entre chaque lecture

except KeyboardInterrupt:
    print("Arrêt du programme")
finally:
    GPIO.cleanup()
    dht_device.exit()