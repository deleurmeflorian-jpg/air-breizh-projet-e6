import mysql.connector

db = mysql.connector.connect(
    host="192.168.1.50",
    user="",
    password="",
    database=""
)

cursor = db.cursor()
cursor.execute("SELECT temperature, humidite, date FROM mesures ORDER BY date DESC LIMIT 5")

for ligne in cursor.fetchall():
    print(ligne)
