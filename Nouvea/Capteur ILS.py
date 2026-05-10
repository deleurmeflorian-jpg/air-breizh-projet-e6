from gpiozero import Button
from time import sleep, time, strftime

# --- Configuration ---
# L'ILS est considéré comme un "Bouton" par la Pi (contact sec)
# pull_up=True remplace GPIO.PUD_UP
capteur_ils = Button(17, pull_up=True, bounce_time=0.2) 

ALERTE_DUREE_SEC = 300  # 5 minutes
temps_debut_ouverture = 0
porte_ouverte = False
def porte_s_ouvre():
    global porte_ouverte, temps_debut_ouverture
    print(f"[{strftime('%H:%M:%S')}] ALERTE : Porte OUVERTE")
    porte_ouverte = True
    temps_debut_ouverture = time()

def porte_se_ferme():
    global porte_ouverte, temps_debut_ouverture
    duree = 0
    if temps_debut_ouverture > 0:
        duree = time() - temps_debut_ouverture
    
    print(f"[{strftime('%H:%M:%S')}] Porte FERMÉE. Durée : {duree:.2f} sec")
    porte_ouverte = False
    temps_debut_ouverture = 0

# --- Assignation des événements ---
# equivalent de add_event_detect
capteur_ils.when_pressed = porte_s_ouvre   # Quand le circuit s'ouvre (si pull_up) ou se ferme
capteur_ils.when_released = porte_se_ferme 

print("Système de surveillance (Gpiozero) démarré...")

try:
    while True:
        # Surveillance de la durée
        if porte_ouverte and temps_debut_ouverture > 0:
            duree_actuelle = time() - temps_debut_ouverture
            if duree_actuelle > ALERTE_DUREE_SEC:
                print(f"!!! ALERTE : Porte ouverte depuis {duree_actuelle:.0f}s !!!")
        
        sleep(1)

except KeyboardInterrupt:
    print("Arrêt")