import RPi.GPIO as GPIO
import time

# --- CONFIGURATION ---
CODE_SECRET = "1234"
PIN_LED_VERTE = 22 #PIN 15
PIN_LED_ROUGE = 27 #PIN 13

# --- INITIALISATION GPIO ---
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_LED_VERTE, GPIO.OUT)
GPIO.setup(PIN_LED_ROUGE, GPIO.OUT)

# S'assurer que tout est éteint au démarrage
GPIO.output(PIN_LED_VERTE, GPIO.LOW)
GPIO.output(PIN_LED_ROUGE, GPIO.LOW)

def clignoter_led(pin, nb_fois=3, vitesse=0.2):
    """Fait clignoter la LED connectée à 'pin'."""
    for _ in range(nb_fois):
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(vitesse)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(vitesse)

# --- PROGRAMME PRINCIPAL ---
print("--- SYSTÈME DE CONTRÔLE D'ACCÈS PRÊT ---")

try:
    while True:
        # Demande la saisie à l'utilisateur
        saisie = input("\nVeuillez saisir le code d'accès : ")
        
        if saisie == CODE_SECRET:
            print(">> ACCÈS AUTORISÉ : Bienvenue !")
            # La LED verte clignote 5 fois pour valider
            clignoter_led(PIN_LED_VERTE, nb_fois=5, vitesse=0.1)
        else:
            print(">> ACCÈS REFUSÉ : Code incorrect.")
            # La LED rouge clignote 3 fois pour signaler l'erreur
            clignoter_led(PIN_LED_ROUGE, nb_fois=3, vitesse=0.2)

except KeyboardInterrupt:
    # Si on appuie sur Ctrl+C, on nettoie les broches proprement
    print("\nArrêt du programme...")
    GPIO.cleanup()