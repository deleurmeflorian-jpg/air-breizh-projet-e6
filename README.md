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
- **Raspberry Pi** (Raspbian) — Python 3, threads concurrents
- **Windows Server 2022** — Hyper-V, machines virtuelles Windows/Linux
- **MariaDB** — base de données `metrologie`
- **Grafana** — tableau de bord de supervision
- Capteurs : DHT20, SDS011, ILS, relais Songle

## Répartition par étudiant

### Étudiant 1 – Florian (capteurs & Raspberry Pi)
- Installation et configuration du Raspberry Pi
- Câblage et mise en œuvre des capteurs (DHT20, SDS011, ILS, relais)
- Développement des scripts Python (lecture capteurs, relais, digicode, BDD)
- Tests et validation du système

### Étudiant 2 – Mathéo (infrastructure & métriques)
- Mise en œuvre de l'environnement Hyper-V (2 hôtes physiques)
- Création de machines virtuelles Windows et Linux
- Collecte des métriques CPU, RAM, température des hôtes et VMs
- Mise en place de l'onduleur Tripp Lite
- Simulation d'attaques et validation des indicateurs

### Étudiant 3 – Eliott (base de données & supervision)
- Conception et gestion de la base de données MariaDB
- Développement des pages PHP (enregistrement et authentification)
- Interface d'administration et de supervision
- Tableau de bord Grafana
- Génération de rapports et centralisation 
