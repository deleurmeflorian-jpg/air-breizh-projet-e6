import RPi.GPIO as GPIO
import time

# --- Configuration ---
PIN_RELAIS = 29        # GPIO5 = Pin physique 29
DELAI = 1              # Secondes entre chaque changement

GPIO.setmode(GPIO.BOARD)          # Numérotation physique des pins
GPIO.setup(PIN_RELAIS, GPIO.OUT)

print("=== Test relais songle ===")
print(f"Pin utilisée : {PIN_RELAIS} (GPIO5)")
print("Branchement multimètre : NO <-> COM  ou  NC <-> COM")
print("Mode résistance (ohmmètre)")
print("Ctrl+C pour arrêter\n")

try:
    while True:
        # --- RELAIS ACTIVÉ (bobine alimentée) ---
        GPIO.output(PIN_RELAIS, GPIO.HIGH)
        print(">>> RELAIS ON  (IN = HIGH) : NO fermé, NC ouvert")
        print("    NO-COM : ~0 Ω  |  NC-COM : ∞ Ω")
        time.sleep(DELAI)

        # --- RELAIS DÉSACTIVÉ (repos) ---
        GPIO.output(PIN_RELAIS, GPIO.LOW)
        print(">>> RELAIS OFF (IN = LOW)  : NO ouvert, NC fermé")
        print("    NO-COM : ∞ Ω  |  NC-COM : ~0 Ω")
        time.sleep(DELAI)

except KeyboardInterrupt:
    print("\nArrêt propre.")

finally:
    GPIO.output(PIN_RELAIS, GPIO.LOW)   # Relais au repos à la sortie
    GPIO.cleanup()
    print("GPIO nettoyé. Fin du programme.")
    
    
    
    