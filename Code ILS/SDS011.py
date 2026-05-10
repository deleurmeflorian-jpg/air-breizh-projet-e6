from sds011 import SDS011
import time

# Adapter si nécessaire (/dev/ttyUSB1, etc.)
capteur = SDS011("/dev/tty0", use_query_mode=True)

while True:
    capteur.sleep(False)
    time.sleep(2)

    pm25, pm10 = capteur.query()

    print(f"PM2.5 : {pm25} µg/m³")
    print(f"PM10  : {pm10} µg/m³")
    print("-" * 30)

    capteur.sleep(True)
    time.sleep(5)
