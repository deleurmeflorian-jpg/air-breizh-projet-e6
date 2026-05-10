import time
import threading
import logging
import os
import mysql.connector
from mysql.connector import Error
import RPi.GPIO as GPIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(threadName)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── CONFIG ────────────────────────────────────────────────
GPIO_FAN, GPIO_VERTE, GPIO_ROUGE, GPIO_ILS = 18, 27, 22, 17
GPIO_RELAIS   = 5        # GPIO5 = Pin physique 29
CODE_SECRET   = "1234"
SEUIL_TEMP    = 26.0
SEUIL_PM25    = 25.0
PORT_SDS011   = "/dev/ttyUSB0"
PIPE_DIGICODE = "/tmp/digicode"
DB = {
    "host": "192.168.101.150",
    "port": 3306,
    "database": "metrologie",
    "user": "usertp",
    "password": "metrologie2026!",
    "connection_timeout": 5
}

# ── ÉTAT PARTAGÉ ──────────────────────────────────────────
lock = threading.Lock()
data = {
    "temp": None,
    "hydro": None,
    "etat_porte": False,
    "etat_ventilo": False,
    "etat_relais": False,
    "concentration_pm25": None,
    "concentration_pm10": None
}
stop = threading.Event()

# ── GPIO ──────────────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(GPIO_VERTE,  GPIO.OUT)
GPIO.setup(GPIO_ROUGE,  GPIO.OUT)
GPIO.setup(GPIO_RELAIS, GPIO.OUT)
GPIO.output(GPIO_VERTE,  GPIO.LOW)
GPIO.output(GPIO_ROUGE,  GPIO.LOW)
GPIO.output(GPIO_RELAIS, GPIO.LOW)   # Relais OFF au démarrage

def clignoter(pin, fois):
    for _ in range(fois):
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.3)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.3)

# ── DIGICODE ──────────────────────────────────────────────
def thread_digicode():
    if not os.path.exists(PIPE_DIGICODE):
        os.mkfifo(PIPE_DIGICODE)
    log.info("Digicade - OK (verte=GPIO%d rouge=GPIO%d)", GPIO_VERTE, GPIO_ROUGE)
    while not stop.is_set():
        try:
            with open(PIPE_DIGICODE, "r") as f:
                code = f.readline().strip()
            if not code:
                continue
            if code == CODE_SECRET:
                log.info("Digicade - CODE CORRECT → LED verte clignote 3 fois")
                clignoter(GPIO_VERTE, fois=3)
            else:
                log.info("Digicade - CODE FAUX → LED rouge clignote 5 fois")
                clignoter(GPIO_ROUGE, fois=5)
        except Exception as e:
            log.error("Digicade - %s", e)
            time.sleep(1)

# ── ILS (PORTE) ───────────────────────────────────────────
def thread_ils():
    GPIO.setup(GPIO_ILS, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log.info("ILS - OK GPIO%d", GPIO_ILS)
    precedent = None
    t_open = None

    while not stop.is_set():
        ouvert = GPIO.input(GPIO_ILS) == GPIO.HIGH
        with lock:
            data["etat_porte"] = ouvert
        log.info("ILS - Porte %s", "OUVERTE" if ouvert else "FERMEE")

        if precedent is not None and ouvert != precedent:
            if ouvert:
                t_open = time.time()
            else:
                duree = int(time.time() - t_open) if t_open else 0
                log.info("ILS - fermee apres %d s", duree)
                if duree > 300:
                    log.warning("ALERTE - porte ouverte plus de 5 min !")

        precedent = ouvert
        time.sleep(2)

# ── DHT20 (TEMPÉRATURE + HUMIDITÉ + RELAIS) ───────────────
_alerte_temp = 0

def thread_dht20():
    global _alerte_temp
    try:
        import board, adafruit_ahtx0, digitalio
        fan = digitalio.DigitalInOut(board.D18)
        fan.direction = digitalio.Direction.OUTPUT
        i2c = board.I2C()
        sensor = adafruit_ahtx0.AHTx0(i2c)
        log.info("DHT20 - OK")
        log.info("RELAIS - OK GPIO%d (seuil %.1f C)", GPIO_RELAIS, SEUIL_TEMP)

        while not stop.is_set():
            t, h = sensor.temperature, sensor.relative_humidity

            # Ventilateur via adafruit digitalio
            fan.value = t > SEUIL_TEMP

            # Relais via RPi.GPIO (même seuil)
            relais_on = t > SEUIL_TEMP
            GPIO.output(GPIO_RELAIS, GPIO.HIGH if relais_on else GPIO.LOW)

            with lock:
                data["temp"]          = t
                data["hydro"]         = h
                data["etat_ventilo"]  = fan.value
                data["etat_relais"]   = relais_on

            log.info(
                "DHT20 - %.1f C | %.1f%% | VENTILO:%s | RELAIS:%s",
                t, h,
                "ON" if fan.value else "OFF",
                "ON" if relais_on  else "OFF"
            )

            if relais_on and time.time() - _alerte_temp > 60:
                log.warning(
                    "ALERTE - temperature %.1f C > seuil %.1f C ! (ventilo + relais actives)",
                    t, SEUIL_TEMP
                )
                _alerte_temp = time.time()

            time.sleep(2)

    except Exception as e:
        log.error("DHT20 - %s", e)
        # Sécurité : relais OFF si le thread plante
        GPIO.output(GPIO_RELAIS, GPIO.LOW)

# ── SDS011 (QUALITÉ AIR) ──────────────────────────────────
_alerte_air = 0

def thread_sds011():
    global _alerte_air
    while not stop.is_set():
        try:
            from sds011 import SDS011
            sensor = SDS011(PORT_SDS011, use_query_mode=True)
            log.info("SDS011 - OK sur %s", PORT_SDS011)
            erreurs = 0

            while not stop.is_set():
                try:
                    sensor.sleep(sleep=False)
                    time.sleep(1)
                    sensor.ser.flushInput()
                    r = sensor.query()
                    sensor.sleep(sleep=True)

                    if r is None:
                        erreurs += 1
                    else:
                        pm25, pm10 = r
                        with lock:
                            data["concentration_pm25"] = pm25
                            data["concentration_pm10"] = pm10
                        log.info("SDS011 - PM2.5:%.1f | PM10:%.1f ug/m3", pm25, pm10)
                        if pm25 > SEUIL_PM25 and time.time() - _alerte_air > 60:
                            log.warning("ALERTE - PM2.5:%.1f ug/m3 > seuil %.1f !", pm25, SEUIL_PM25)
                            _alerte_air = time.time()
                        erreurs = 0
                except Exception as e:
                    log.error("SDS011 - %s", e)
                    erreurs += 1

                if erreurs >= 5:
                    log.warning("SDS011 - 5 erreurs, reinit dans 15 s...")
                    break

                time.sleep(2)

        except Exception as e:
            log.error("SDS011 - init : %s", e)
        time.sleep(15)

# ── BDD (ENVOI MYSQL) ─────────────────────────────────────
_bdd_fail = 0

def thread_bdd():
    global _bdd_fail
    while not stop.is_set():
        with lock:
            t       = data["temp"]
            h       = data["hydro"]
            pm25    = data["concentration_pm25"]
            pm10    = data["concentration_pm10"]
            porte   = data["etat_porte"]
            ventilo = data["etat_ventilo"]
            relais  = data["etat_relais"]

        if t is not None and pm25 is not None:
            if time.time() - _bdd_fail > 60:
                try:
                    conn = mysql.connector.connect(**DB)
                    cur  = conn.cursor()
                    cur.execute(
                        "INSERT INTO mesures "
                        "(temperature, humidite, pm25, pm10, etat_porte, etat_ventilo, etat_relais) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (t, h, pm25, pm10, int(porte), int(ventilo), int(relais))
                    )
                    conn.commit()
                    cur.close()
                    conn.close()
                    log.info(
                        "BDD - enregistre temp=%.1f C hum=%.1f%% pm25=%.1f ug/m3 ventilo=%s relais=%s",
                        t, h, pm25,
                        "ON" if ventilo else "OFF",
                        "ON" if relais  else "OFF"
                    )
                except Error as e:
                    log.warning("BDD - erreur : %s", e)
                    _bdd_fail = time.time()

        for _ in range(30):
            if stop.is_set():
                break
            time.sleep(1)

# ── DÉMARRAGE ─────────────────────────────────────────────
if __name__ == "__main__":
    log.info("STATION - DEMARRAGE")
    threads = [
        threading.Thread(target=thread_ils,      name="ILS",      daemon=True),
        threading.Thread(target=thread_dht20,    name="DHT20",    daemon=True),
        threading.Thread(target=thread_sds011,   name="SDS011",   daemon=True),
        threading.Thread(target=thread_bdd,      name="BDD",      daemon=True),
        threading.Thread(target=thread_digicode, name="Digicade", daemon=True),
    ]
    for t in threads:
        t.start()
        time.sleep(0.5)
    log.info("Tous les modules actifs.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Arret...")
        stop.set()
        for t in threads:
            t.join(timeout=5)
        GPIO.output(GPIO_VERTE,  GPIO.LOW)
        GPIO.output(GPIO_ROUGE,  GPIO.LOW)
        GPIO.output(GPIO_RELAIS, GPIO.LOW)   # Relais OFF à l'arrêt
        GPIO.cleanup()
        log.info("Arret propre.")
