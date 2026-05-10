from gpiozero import Button
import time

# On définit le capteur sur GPIO 17 (Pin 11)
capteur = Button(17, pull_up=True)

print("--- TEST DIRECT ---")
print("Capteur ILS")

while True:
    if capteur.is_pressed:
        print("ÉTAT : CONTACT ÉTABLI (Fermé)")
    else:
        print("ÉTAT : CIRCUIT OUVERT (Ouvert)")
    time.sleep(0.1)