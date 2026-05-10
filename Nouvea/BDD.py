import mysql.connector
from datetime import datetime

# Configuration fournie par l'étudiant 3
DB_CONFIG = {
    'host': '192.168.101.150', # IP du serveur central
    'user': 'root',
    'password': 'admin',
    'database': 'metrologie'
}

def enregistrer_donnees(temp, hum, pm25, etat_porte):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        query = """
        INSERT INTO releves_environnement 
        (date_heure, temperature, hygrometrie, particules_fines, porte_ouverte) 
        VALUES (%s, %s, %s, %s, %s)
        """
        
        valeurs = (datetime.now(), temp, hum, pm25, etat_porte)
        
        cursor.execute(query, valeurs)
        conn.commit()
        print("Données sauvegardées en BDD.")
        
    except mysql.connector.Error as err:
        print(f"Erreur SQL : {err}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# Exemple d'appel (à intégrer dans la boucle principale)
# enregistrer_donnees(24.5, 45, 12.0, False)