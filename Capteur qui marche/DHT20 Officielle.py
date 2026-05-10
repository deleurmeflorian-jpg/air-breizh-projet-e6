import time
import board
import adafruit_ahtx0

# On récupère l'accès au bus I2C
i2c = board.I2C()

print("--- Tentative de déblocage du capteur ---")

# 1. On essaie de forcer un reset manuel via des commandes brutes
try:
    while not i2c.try_lock():
        pass
    # Commande magique de reset pour AHT20 (0xBA)
    i2c.writeto(0x38, bytes([0xBA])) 
    time.sleep(0.5) # On laisse respirer
    i2c.unlock()
    print("Reset manuel envoyé...")
except Exception as e:
    print(f"Impossible d'envoyer le reset : {e}")

# 2. Maintenant on essaie de charger la bibliothèque
try:
    sensor = adafruit_ahtx0.AHTx0(i2c)
    print("\n SUCCÈS ! Capteur connecté.")
    
    while True:
        print(f"Temp: {sensor.temperature:.1f}°C  |  Hum: {sensor.relative_humidity:.1f}%")
        time.sleep(2)

except Exception as e:
    print(f"\n ÉCHEC : {e}")
    print("Si ça ne marche pas, passe à la solution 2 (baisser la vitesse).")