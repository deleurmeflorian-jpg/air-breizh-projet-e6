# Air-Breizh – Contrôle environnemental d'une baie serveur

## Contexte
Projet réalisé dans le cadre du BTS CIEL option IR (Informatique et Réseaux), session 2026.  
Client : **Air-Breizh**, association de surveillance de la qualité de l'air basée à Cesson-Sévigné (35).

## Objectif
Mettre en place un système de contrôle environnemental d'une baie serveur via un Raspberry Pi :
- Mesure de la température et de l'hygrométrie (capteur DHT20)
- Détection de particules fines PM2.5 / PM10 (capteur SDS011)
- Détection d'ouverture de porte (capteur magnétique ILS)
- Commande d'un ventilateur via relais (déclenchement au-dessus de 26°C)
- Authentification par digicode USB avec retour lumineux (LED verte/rouge)
- Enregistrement des données dans une base MariaDB

## Technologies utilisées
- **Raspberry Pi** (Raspbian)
- **Python 3** (threads concurrents)
- **MariaDB** (base de données `metrologie`)
- Capteurs : DHT20, SDS011, ILS, relais Songle

## Mon rôle (Étudiant 1)
- Installation et configuration du Raspberry Pi
- Câblage et mise en œuvre de tous les capteurs
- Développement des scripts Python (lecture capteurs, relais, digicode, BDD)
- Tests et validation du système

## 🔗 Projet réalisé en équipe de 3 étudiants
