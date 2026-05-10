from gpiozero import Button
from signal import pause
from datetime import datetime

# Configuration du capteur ILS (Porte) sur le GPIO 17

porte = Button(17, pull_up=True)

def porte_ouverte():
    temps = datetime.now().strftime("%H:%M:%S")
    print(f"[{temps}] Alerte : La porte a été OUVERTE !")

def porte_fermee():
    temps = datetime.now().strftime("%H:%M:%S")
    print(f"[{temps}] Info : La porte est désormais FERMÉE.")

# Utilisation des callbacks (évènements)
porte.when_pressed = porte_ouverte
porte.when_released = porte_fermee

print("--- Système de surveillance activé ---")
print("En attente de détection sur le GPIO 17...")

try:
    pause()
except KeyboardInterrupt:
    print("\nArrêt du programme par l'utilisateur.")