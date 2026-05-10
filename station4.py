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
GPIO_VENTILO  = 18   # Ventilateur
GPIO_VERTE    = 27   # LED verte  (digicode correct)
GPIO_ROUGE    = 22   # LED rouge  (digicode faux)
GPIO_ILS      = 17   # Capteur ILS (porte)
GPIO_RELAIS   = 5    # Relais (BCM 5 = pin physique 29)

CODE_SECRET   = "1234"
SEUIL_TEMP    = 26.0          # °C  — ventilateur ON au-dessus, OFF en dessous
SEUIL_PM25    = 25.0          # ug/m3
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

# Intervalle entre chaque insertion en base (secondes)
BDD_INTERVALLE = 30

# ── ETAT PARTAGE ──────────────────────────────────────────────────────────────
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
GPIO.setup(GPIO_VENTILO, GPIO.OUT)
GPIO.setup(GPIO_VERTE,   GPIO.OUT)
GPIO.setup(GPIO_ROUGE,   GPIO.OUT)
GPIO.setup(GPIO_RELAIS,  GPIO.OUT)
GPIO.output(GPIO_VENTILO, GPIO.LOW)
GPIO.output(GPIO_VERTE,   GPIO.LOW)
GPIO.output(GPIO_ROUGE,   GPIO.LOW)
GPIO.output(GPIO_RELAIS,  GPIO.LOW)
log.info("GPIO initialise - VENTILO:GPIO%d VERTE:GPIO%d ROUGE:GPIO%d RELAIS:GPIO%d ILS:GPIO%d",
         GPIO_VENTILO, GPIO_VERTE, GPIO_ROUGE, GPIO_RELAIS, GPIO_ILS)

# ── UTILITAIRE ────────────────────────────────────────────────────────────────
def clignoter(pin, fois, duree=0.3):
    for _ in range(fois):
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(duree)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(duree)

# ── THREAD DIGICODE ───────────────────────────────────────────────────────────
def thread_digicode():
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
                log.info("Digicode - CODE CORRECT -> LED verte x3")
                clignoter(GPIO_VERTE, 3)
            else:
                log.info("Digicode - CODE FAUX '%s' -> LED rouge x5", code)
                clignoter(GPIO_ROUGE, 5)
        except Exception as e:
            log.error("Digicode - %s", e)
            time.sleep(1)

# ── THREAD ILS (PORTE) ────────────────────────────────────────────────────────
def thread_ils():
    GPIO.setup(GPIO_ILS, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log.info("ILS - OK GPIO%d", GPIO_ILS)
    precedent   = None
    t_ouverture = None
    while not stop.is_set():
        ouvert = GPIO.input(GPIO_ILS) == GPIO.HIGH
        with lock:
            data["etat_porte"] = ouvert
        log.info("ILS - Porte : %s", "OUVERTE" if ouvert else "FERMEE")
        if precedent is not None and ouvert != precedent:
            if ouvert:
                t_ouverture = time.time()
                log.info("ILS - >>> PORTE VIENT DE S'OUVRIR <<<")
            else:
                if t_ouverture is not None:
                    duree = int(time.time() - t_ouverture)
                    log.info("ILS - >>> PORTE VIENT DE SE FERMER (etait ouverte %d s) <<<", duree)
                    if duree > 300:
                        log.warning("ILS - ALERTE : porte etait ouverte plus de 5 min !")
                t_ouverture = None
        if ouvert and t_ouverture is not None:
            duree_courante = int(time.time() - t_ouverture)
            if duree_courante > 300:
                log.warning("ILS - ALERTE : porte ouverte depuis %d s !", duree_courante)
        precedent = ouvert
        time.sleep(2)

# ── THREAD DHT20 ──────────────────────────────────────────────────────────────
_alerte_temp = 0.0

def thread_dht20():
    global _alerte_temp
    try:
        import board
        import adafruit_ahtx0
        i2c     = board.I2C()
        capteur = adafruit_ahtx0.AHTx0(i2c)
        log.info("DHT20 - capteur detecte sur I2C")
        log.info("DHT20 - seuil : %.1f C  |  VENTILO GPIO%d  |  RELAIS GPIO%d",
                 SEUIL_TEMP, GPIO_VENTILO, GPIO_RELAIS)
        while not stop.is_set():
            temperature = capteur.temperature
            humidite    = capteur.relative_humidity
            if temperature > SEUIL_TEMP:
                GPIO.output(GPIO_VENTILO, GPIO.HIGH)
                GPIO.output(GPIO_RELAIS,  GPIO.HIGH)
                ventilo_on = True
                relais_on  = True
            else:
                GPIO.output(GPIO_VENTILO, GPIO.LOW)
                GPIO.output(GPIO_RELAIS,  GPIO.LOW)
                ventilo_on = False
                relais_on  = False
            with lock:
                data["temp"]         = round(temperature, 2)
                data["hydro"]        = round(humidite, 2)
                data["etat_ventilo"] = ventilo_on
                data["etat_relais"]  = relais_on
            log.info("DHT20 - %.1f C | %.1f %% | VENTILO:%s | RELAIS:%s",
                     temperature, humidite,
                     "ON " if ventilo_on else "OFF",
                     "ON " if relais_on  else "OFF")
            if ventilo_on and (time.time() - _alerte_temp) > 60:
                log.warning("ALERTE - temperature %.1f C depasse %.1f C"
                            " (ventilateur + relais actives)", temperature, SEUIL_TEMP)
                _alerte_temp = time.time()
            time.sleep(2)
    except Exception as e:
        log.error("DHT20 - erreur fatale : %s", e)
        GPIO.output(GPIO_VENTILO, GPIO.LOW)
        GPIO.output(GPIO_RELAIS,  GPIO.LOW)
        with lock:
            data["etat_ventilo"] = False
            data["etat_relais"]  = False

# ── THREAD SDS011 ─────────────────────────────────────────────────────────────
_alerte_air = 0.0

def thread_sds011():
    global _alerte_air
    while not stop.is_set():
        try:
            from sds011 import SDS011
            capteur = SDS011(PORT_SDS011, use_query_mode=True)
            log.info("SDS011 - OK sur %s", PORT_SDS011)
            erreurs = 0
            while not stop.is_set():
                try:
                    capteur.sleep(sleep=False)
                    time.sleep(1)
                    capteur.ser.flushInput()
                    result = capteur.query()
                    capteur.sleep(sleep=True)
                    if result is None:
                        log.warning("SDS011 - reponse vide")
                        erreurs += 1
                    else:
                        pm25, pm10 = result
                        with lock:
                            data["concentration_pm25"] = round(pm25, 2)
                            data["concentration_pm10"] = round(pm10, 2)
                        log.info("SDS011 - PM2.5:%.1f | PM10:%.1f ug/m3", pm25, pm10)
                        erreurs = 0
                        if pm25 > SEUIL_PM25 and (time.time() - _alerte_air) > 60:
                            log.warning("ALERTE - PM2.5 %.1f ug/m3 depasse %.1f ug/m3 !",
                                        pm25, SEUIL_PM25)
                            _alerte_air = time.time()
                except Exception as e:
                    log.error("SDS011 - lecture : %s", e)
                    erreurs += 1
                if erreurs >= 5:
                    log.warning("SDS011 - 5 erreurs consecutives, reinitialisation dans 15 s...")
                    break
                time.sleep(2)
        except Exception as e:
            log.error("SDS011 - initialisation : %s", e)
        time.sleep(15)

# ── THREAD BDD ────────────────────────────────────────────────────────────────
def bdd_connecter():
    """Tente une connexion MySQL, retourne (conn, cur) ou (None, None)."""
    try:
        conn = mysql.connector.connect(**DB)
        cur  = conn.cursor()
        log.info("BDD - connexion etablie avec %s", DB["host"])
        return conn, cur
    except Error as e:
        log.error("BDD - impossible de se connecter : %s", e)
        return None, None

def thread_bdd():
    """
    Toutes les BDD_INTERVALLE secondes :
      1. Lit les donnees partagees
      2. Remplace les valeurs None par 0.0 (capteur absent ne bloque pas)
      3. Tente l'INSERT avec reconnexion automatique en cas d'echec
      4. Attend BDD_INTERVALLE secondes avant la prochaine insertion
    """
    log.info("BDD - demarrage (intervalle : %d s)", BDD_INTERVALLE)

    # Connexion initiale avec retry toutes les 10 s
    conn, cur = None, None
    while not stop.is_set() and conn is None:
        conn, cur = bdd_connecter()
        if conn is None:
            log.warning("BDD - nouvelle tentative dans 10 s...")
            time.sleep(10)

    while not stop.is_set():
        # 1. Lecture des donnees partagees
        with lock:
            t       = data["temp"]
            h       = data["hydro"]
            pm25    = data["concentration_pm25"]
            pm10    = data["concentration_pm10"]
            porte   = data["etat_porte"]
            ventilo = data["etat_ventilo"]
            relais  = data["etat_relais"]

        # 2. Attendre que le DHT20 ait au moins une mesure
        if t is None:
            log.info("BDD - attente DHT20 (temp=None)...")
            time.sleep(5)
            continue

        # PM2.5/PM10 : si capteur absent, on insere 0.0 pour ne pas bloquer
        pm25 = pm25 if pm25 is not None else 0.0
        pm10 = pm10 if pm10 is not None else 0.0

        # 3. INSERT avec reconnexion automatique
        inserted = False
        tentatives = 0
        while not inserted and tentatives < 3 and not stop.is_set():
            tentatives += 1
            try:
                # Reconnexion si la connexion a ete perdue
                if conn is None or not conn.is_connected():
                    log.warning("BDD - connexion perdue, reconnexion...")
                    conn, cur = bdd_connecter()
                    if conn is None:
                        log.error("BDD - reconnexion echouee (tentative %d/3)", tentatives)
                        time.sleep(5)
                        continue

                cur.execute(
                    "INSERT INTO mesures "
                    "(temperature, humidite, pm25, pm10, etat_porte, etat_ventilo, etat_relais) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (t, h, pm25, pm10, int(porte), int(ventilo), int(relais))
                )
                conn.commit()
                inserted = True
                log.info(
                    "BDD - OK enregistre | %.1f C | %.1f %% | "
                    "PM2.5:%.1f | PM10:%.1f | "
                    "ventilo:%s | relais:%s | porte:%s",
                    t, h, pm25, pm10,
                    "ON"  if ventilo else "OFF",
                    "ON"  if relais  else "OFF",
                    "OUV" if porte   else "FERM"
                )
            except Error as e:
                log.error("BDD - erreur INSERT (tentative %d/3) : %s", tentatives, e)
                # Fermer la connexion cassee pour forcer une reconnexion
                try:
                    if conn:
                        conn.close()
                except Exception:
                    pass
                conn, cur = None, None
                time.sleep(3)

        if not inserted:
            log.warning("BDD - insertion abandonnee apres 3 tentatives, prochaine dans %d s", BDD_INTERVALLE)

        # 4. Attente avant prochaine insertion
        for _ in range(BDD_INTERVALLE):
            if stop.is_set():
                break
            time.sleep(1)

    # Fermeture propre
    try:
        if conn and conn.is_connected():
            cur.close()
            conn.close()
            log.info("BDD - connexion fermee proprement")
    except Exception:
        pass

# ── DEMARRAGE ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=" * 55)
    log.info("  STATION METROLOGIE - DEMARRAGE")
    log.info("  Seuil temperature : %.1f C", SEUIL_TEMP)
    log.info("  Seuil PM2.5       : %.1f ug/m3", SEUIL_PM25)
    log.info("=" * 55)

    threads = [
        threading.Thread(target=thread_ils,      name="ILS",      daemon=True),
        threading.Thread(target=thread_dht20,    name="DHT20",    daemon=True),
        threading.Thread(target=thread_sds011,   name="SDS011",   daemon=True),
        threading.Thread(target=thread_bdd,      name="BDD",      daemon=True),
        threading.Thread(target=thread_digicode, name="Digicode", daemon=True),
    ]

    for t in threads:
        t.start()
        time.sleep(0.5)

    log.info("Tous les modules sont actifs. Ctrl+C pour arreter.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Arret demande...")
        stop.set()
        for t in threads:
            t.join(timeout=5)
        GPIO.output(GPIO_VENTILO, GPIO.LOW)
        GPIO.output(GPIO_VERTE,   GPIO.LOW)
        GPIO.output(GPIO_ROUGE,   GPIO.LOW)
        GPIO.output(GPIO_RELAIS,  GPIO.LOW)
        GPIO.cleanup()
        log.info("Arret propre.")