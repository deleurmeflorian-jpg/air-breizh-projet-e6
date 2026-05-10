import time
import board
import adafruit_dht20

# Initialisation du capteur DHT20
i2c = board.I2C()
dht20 = adafruit_dht20.DHT20(i2c)

while True:
    temperature = dht20.temperature
    humidity = dht20.relative_humidity

    print(f"Température : {temperature:.1f} °C")
    print(f"Humidité    : {humidity:.1f} %")
    print("-" * 30)

    time.sleep(2)
