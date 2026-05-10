import time
import threading
import logging
import os
import mysql.connector
from mysql.connector import Error
import RPi.GPIO as GPIO

# ── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
GPIO_FAN    = 18   # Ventilateur
GPIO_VERTE  = 27   # LED verte  (digicode OK)
GPIO_ROUGE  = 22   # LED rouge  (digicode KO)
GPIO_ILS    = 17   # Capteur ILS (porte)
GPIO_RELAIS = 5    # Relais (BCM 5 = pin physique 29)

CODE_SECRET   = "1234"
SEUIL_TEMP    = 26.0          # °C  → ventilateur + relais s'activent au-dessus
SEUIL_PM25    = 25.0          # µg/m³
PORT_SDS011   = "/dev/ttyUSB0"
PIPE_DIGICODE = "/tmp/digicode"

DB = {
    "host":               "192.168.101.150",
    "port":               3306,
    "database":           "metrologie",
    "user":               "usertp",
    "password":           "metrologie2026!",
    "connection_timeout": 5,
}

# ── ÉTAT PARTAGÉ ──────────────────────────────────────────────────────────────
lock = threading.Lock()
data = {
    "temp":               None,
    "hydro":              None,
    "etat_porte":         False,
    "etat_ventilo":       False,
    "etat_relais":        False,
    "concentration_pm25": None,
    "concentration_pm10": None,
}
stop = threading.Event()

# ── INITIALISATION GPIO ───────────────────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Sorties
for pin in (GPIO_FAN, GPIO_VERTE, GPIO_ROUGE, GPIO_RELAIS):
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)   # tout éteint au démarrage

log.info(
    "GPIO - initialisé (FAN=%d VERTE=%d ROUGE=%d RELAIS=%d ILS=%d)",
    GPIO_FAN, GPIO_VERTE, GPIO_ROUGE, GPIO_RELAIS, GPIO_ILS
)

# ── UTILITAIRES ───────────────────────────────────────────────────────────────
def clignoter(pin: int, fois: int, duree: float = 0.3) -> None:
    """Fait clignoter une LED <fois> fois."""
    for _ in range(fois):
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(duree)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(duree)

# ── THREAD DIGICODE ───────────────────────────────────────────────────────────
def thread_digicode() -> None:
    """
    Lit les codes saisis depuis le FIFO /tmp/digicode.
    - Code correct → LED verte clignote 3 fois
    - Code faux    → LED rouge clignote 5 fois
    """
    if not os.path.exists(PIPE_DIGICODE):
        os.mkfifo(PIPE_DIGICODE)
    log.info("Digicode - en attente sur %s", PIPE_DIGICODE)

    while not stop.is_set():
        try:
            with open(PIPE_DIGICODE, "r") as f:
                code = f.readline().strip()
            if not code:
                continue
            if code == CODE_SECRET:
                log.info("Digicode - CODE CORRECT → LED verte x3")
                clignoter(GPIO_VERTE, 3)
            else:
                log.info("Digicode - CODE FAUX '%s' → LED rouge x5", code)
                clignoter(GPIO_ROUGE, 5)
        except Exception as e:
            log.error("Digicode - erreur : %s", e)
            time.sleep(1)

# ── THREAD ILS (PORTE) ────────────────────────────────────────────────────────
def thread_ils() -> None:
    """
    Surveille l'état de la porte via le capteur ILS (GPIO_ILS).
    Déclenche une alerte si la porte reste ouverte plus de 5 minutes.
    """
    GPIO.setup(GPIO_ILS, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log.info("ILS - OK GPIO%d", GPIO_ILS)

    precedent = None
    t_ouverture = None

    while not stop.is_set():
        ouvert = GPIO.input(GPIO_ILS) == GPIO.HIGH

        with lock:
            data["etat_porte"] = ouvert

        # Log uniquement sur changement d'état
        if ouvert != precedent:
            log.info("ILS - Porte %s", "OUVERTE" if ouvert else "FERMEE")
            if ouvert:
                t_ouverture = time.time()
            elif t_ouverture is not None:
                duree = int(time.time() - t_ouverture)
                log.info("ILS - durée ouverture : %d s", duree)
                if duree > 300:
                    log.warning("ALERTE - porte ouverte plus de 5 min !")
                t_ouverture = None

        # Alerte continue si porte toujours ouverte depuis > 5 min
        if ouvert and t_ouverture is not None:
            if time.time() - t_ouverture > 300:
                log.warning("ALERTE - porte toujours ouverte (%d s) !", int(time.time() - t_ouverture))

        precedent = ouvert
        time.sleep(2)

# ── THREAD DHT20 (TEMPÉRATURE + HUMIDITÉ + VENTILATEUR + RELAIS) ─────────────
_alerte_temp = 0.0

def thread_dht20() -> None:
    """
    Lit la température et l'humidité via le capteur DHT20 (AHTx0 sur I2C).

    Logique ventilateur + relais :
        température > SEUIL_TEMP (26 °C)  →  GPIO_FAN = HIGH  +  GPIO_RELAIS = HIGH
        température ≤ SEUIL_TEMP          →  GPIO_FAN = LOW   +  GPIO_RELAIS = LOW
    """
    global _alerte_temp
    try:
        import board
        import adafruit_ahtx0

        i2c    = board.I2C()
        sensor = adafruit_ahtx0.AHTx0(i2c)
        log.info("DHT20 - capteur détecté sur I2C")
        log.info("DHT20 - seuil thermique %.1f °C → FAN(GPIO%d) + RELAIS(GPIO%d)", SEUIL_TEMP, GPIO_FAN, GPIO_RELAIS)

        while not stop.is_set():
            t = sensor.temperature
            h = sensor.relative_humidity

            # ── Décision ventilateur + relais ──────────────────────────────
            activer = t > SEUIL_TEMP
            GPIO.output(GPIO_FAN,    GPIO.HIGH if activer else GPIO.LOW)
            GPIO.output(GPIO_RELAIS, GPIO.HIGH if activer else GPIO.LOW)

            with lock:
                data["temp"]         = round(t, 2)
                data["hydro"]        = round(h, 2)
                data["etat_ventilo"] = activer
                data["etat_relais"]  = activer

            log.info(
                "DHT20 - %.1f °C | %.1f %% | VENTILO:%s | RELAIS:%s",
                t, h,
                "ON " if activer else "OFF",
                "ON " if activer else "OFF",
            )

            # Alerte toutes les 60 s si seuil dépassé
            if activer and (time.time() - _alerte_temp) > 60:
                log.warning(
                    "ALERTE - température %.1f °C > seuil %.1f °C  (ventilo + relais activés)",
                    t, SEUIL_TEMP
                )
                _alerte_temp = time.time()

            time.sleep(2)

    except Exception as e:
        log.error("DHT20 - erreur fatale : %s", e)
        # Sécurité : tout éteindre
        GPIO.output(GPIO_FAN,    GPIO.LOW)
        GPIO.output(GPIO_RELAIS, GPIO.LOW)
        with lock:
            data["etat_ventilo"] = False
            data["etat_relais"]  = False

# ── THREAD SDS011 (QUALITÉ DE L'AIR) ─────────────────────────────────────────
_alerte_air = 0.0

def thread_sds011() -> None:
    """
    Lit les concentrations PM2.5 et PM10 via le capteur SDS011.
    Tente une réinitialisation toutes les 15 s en cas d'erreur répétée.
    """
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
                    result = sensor.query()
                    sensor.sleep(sleep=True)

                    if result is None:
                        log.warning("SDS011 - réponse vide")
                        erreurs += 1
                    else:
                        pm25, pm10 = result
                        with lock:
                            data["concentration_pm25"] = round(pm25, 2)
                            data["concentration_pm10"] = round(pm10, 2)
                        log.info("SDS011 - PM2.5:%.1f | PM10:%.1f µg/m³", pm25, pm10)
                        erreurs = 0

                        if pm25 > SEUIL_PM25 and (time.time() - _alerte_air) > 60:
                            log.warning(
                                "ALERTE - PM2.5:%.1f µg/m³ > seuil %.1f µg/m³ !",
                                pm25, SEUIL_PM25
                            )
                            _alerte_air = time.time()

                except Exception as e:
                    log.error("SDS011 - lecture : %s", e)
                    erreurs += 1

                if erreurs >= 5:
                    log.warning("SDS011 - 5 erreurs consécutives → réinitialisation dans 15 s")
                    break

                time.sleep(2)

        except Exception as e:
            log.error("SDS011 - initialisation : %s", e)

        time.sleep(15)

# ── THREAD BDD (ENVOI MYSQL) ──────────────────────────────────────────────────
_bdd_fail = 0.0

def thread_bdd() -> None:
    """
    Envoie toutes les 30 s les mesures en base MySQL si les capteurs
    ont retourné des données valides.
    En cas d'erreur de connexion, attend 60 s avant de réessayer.
    """
    global _bdd_fail

    while not stop.is_set():
        # Lecture atomique de l'état partagé
        with lock:
            t       = data["temp"]
            h       = data["hydro"]
            pm25    = data["concentration_pm25"]
            pm10    = data["concentration_pm10"]
            porte   = data["etat_porte"]
            ventilo = data["etat_ventilo"]
            relais  = data["etat_relais"]

        # N'écrire que si les deux capteurs principaux ont des données
        if t is not None and pm25 is not None:
            if (time.time() - _bdd_fail) > 60:
                try:
                    conn = mysql.connector.connect(**DB)
                    cur  = conn.cursor()
                    cur.execute(
                        "INSERT INTO mesures "
                        "(temperature, humidite, pm25, pm10, etat_porte, etat_ventilo, etat_relais) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (t, h, pm25, pm10, int(porte), int(ventilo), int(relais))
                    )
                    conn.commit()
                    cur.close()
                    conn.close()
                    log.info(
                        "BDD - enregistré | temp=%.1f°C hum=%.1f%% pm25=%.1f pm10=%.1f "
                        "ventilo=%s relais=%s porte=%s",
                        t, h, pm25, pm10,
                        "ON" if ventilo else "OFF",
                        "ON" if relais  else "OFF",
                        "OUV" if porte  else "FERM",
                    )
                except Error as e:
                    log.warning("BDD - erreur connexion : %s (pause 60 s)", e)
                    _bdd_fail = time.time()
        else:
            log.debug("BDD - données insuffisantes, attente capteurs...")

        # Attente interruptible de 30 s
        for _ in range(30):
            if stop.is_set():
                break
            time.sleep(1)

# ── POINT D'ENTRÉE ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=" * 60)
    log.info("STATION MÉTROLOGIE - DÉMARRAGE")
    log.info("Seuil température : %.1f °C", SEUIL_TEMP)
    log.info("Seuil PM2.5       : %.1f µg/m³", SEUIL_PM25)
    log.info("=" * 60)

    threads = [
        threading.Thread(target=thread_ils,      name="ILS",      daemon=True),
        threading.Thread(target=thread_dht20,    name="DHT20",    daemon=True),
        threading.Thread(target=thread_sds011,   name="SDS011",   daemon=True),
        threading.Thread(target=thread_bdd,      name="BDD",      daemon=True),
        threading.Thread(target=thread_digicode, name="Digicode", daemon=True),
    ]

    for t in threads:
        t.start()
        time.sleep(0.5)   # décalage léger pour éviter les conflits I2C/GPIO au boot

    log.info("Tous les modules sont actifs. Ctrl+C pour arrêter.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Arrêt demandé...")
        stop.set()

        for t in threads:
            t.join(timeout=5)

        # Extinction propre de toutes les sorties
        for pin in (GPIO_FAN, GPIO_VERTE, GPIO_ROUGE, GPIO_RELAIS):
            GPIO.output(pin, GPIO.LOW)
        GPIO.cleanup()
        log.info("Arrêt propre. Au revoir.")