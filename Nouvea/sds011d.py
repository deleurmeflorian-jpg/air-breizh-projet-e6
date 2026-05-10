import serial
import time

# Sur ton système, c'est ttyS0 pour les pins 8/10
PORT = "/dev/ttyS0" 

def lire_sds_direct():
    try:
        # On ouvre le port avec un timeout court pour ne pas bloquer
        ser = serial.Serial(PORT, baudrate=9600, timeout=1)
        
        # On lit 10 octets d'un coup
        res = ser.read(10)
        
        if len(res) == 10 and res[0] == 0xAA and res[1] == 0xC0:
            # Formule officielle du SDS011
            pm25 = (res[3] * 256 + res[2]) / 10.0
            pm10 = (res[5] * 256 + res[4]) / 10.0
            return pm25, pm10
            
        ser.close()
    except Exception as e:
        print(f"Erreur port : {e}")
    return None, None

print("--- TEST SDS011 ULTIME ---")

try:
    while True:
        p25, p10 = lire_sds_direct()
        if p25 is not None:
            print(f"SUCCÈS > PM2.5: {p25} | PM10: {p10}")
        else:
            print("Signal instable... Vérifiez que TX est sur Pin 10 et RX sur Pin 8")
        time.sleep(1)
except KeyboardInterrupt:
    print("Arrêt")