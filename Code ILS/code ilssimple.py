import RPi.GPIO as GPIO
import time

# --- Configuration ---
PIN_ILS = 17
ALERTE_DUREE_SEC = 300  # 5 minutes selon le cahier des charges 

# Variables globales pour le suivi du temps
porte_ouverte = False
temps_debut_ouverture = 0

def configuration_gpio():
    GPIO.setmode(GPIO.BCM)
    # PUD_UP : La broche lit 1 (3.3V) par défaut.
    # L'ILS doit connecter la broche à la masse (GND) quand l'aimant est proche (porte fermée).
    GPIO.setup(PIN_ILS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def gestion_etat_porte(channel):
    """
    Fonction appelée automatiquement lors d'un changement d'état (Interruption)
    """
    global porte_ouverte, temps_debut_ouverture
    
    # Lecture de l'état actuel (attention aux rebonds, on relit pour confirmer)
    etat_actuel = GPIO.input(PIN_ILS)

    if etat_actuel == 1: # Si 1 (HIGH), le circuit est ouvert -> Porte OUVERTE
        print(f"[{time.strftime('%H:%M:%S')}] ALERTE : Porte OUVERTE")
        porte_ouverte = True
        temps_debut_ouverture = time.time()
        
    else: # Si 0 (LOW), le circuit est fermé à la masse -> Porte FERMÉE
        duree = 0
        if temps_debut_ouverture > 0:
            duree = time.time() - temps_debut_ouverture
        
        print(f"[{time.strftime('%H:%M:%S')}] Porte FERMÉE. Durée d'ouverture : {duree:.2f} sec")
        porte_ouverte = False
        temps_debut_ouverture = 0

def boucle_principale():
    try:
        # Détection des fronts montants (fermeture->ouverture) et descendants (ouverture->fermeture)
        # bouncetime=200ms permet d'ignorer les parasites mécaniques de l'ILS
        GPIO.add_event_detect(PIN_ILS, GPIO.BOTH, callback=gestion_etat_porte, bouncetime=200)
        
        print("Système de surveillance de porte démarré. (CTRL+C pour quitter)")
        
        while True:
            # Cette boucle sert à surveiller la DURÉE si la porte est restée ouverte
            if porte_ouverte and temps_debut_ouverture > 0:
                duree_actuelle = time.time() - temps_debut_ouverture
                
                # Vérification de la contrainte > 5 minutes 
                if duree_actuelle > ALERTE_DUREE_SEC:
                    print(f"!!! ALERTE CRITIQUE : Porte ouverte depuis plus de 5 minutes ({duree_actuelle:.0f}s) !!!")
                    # Ici, vous pourrez ajouter l'envoi vers la base de données ou un email
                    # [cite: 193] Des alertes seront affichées... avec envoi par mail.
            
            time.sleep(1) # Pause pour économiser le CPU dans la boucle de surveillance

    except KeyboardInterrupt:
        print("\nArrêt du programme...")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    configuration_gpio()
    boucle_principale()