# Solanal

Solanal est un outil Python pour détecter les annonces de véhicules en Suisse romande, autour de Martigny, qui semblent nettement sous le prix du marché Argus/Eurotax.

## Fonctionnalités

- Recherche d'annonces AutoScout24 autour du code postal 1920 (Martigny) avec rayon configurable.
- Mode hors ligne par CSV pour analyser des annonces exportées depuis n'importe quelle plateforme.
- Comparaison avec un CSV de valeurs Argus/Eurotax acquis ou exporté légalement.
- Classement des opportunités selon la décote, les frais de revente estimés, le kilométrage et la distance.

> Remarque: les cotes Argus/Eurotax suisses sont des données commerciales. Le programme ne contourne pas de paywall et ne scrape pas de service protégé; il attend un export CSV fourni par l'utilisateur.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Console interactive pour tester avec de vraies annonces

Lancez la console locale si vous voulez tester sans retenir les options CLI:

```bash
python -m solanal.console
```

La console vous demande d'abord le chemin vers votre vrai fichier Argus/Eurotax. Ensuite, vous pouvez soit chercher des annonces AutoScout24 en direct autour de Martigny, soit importer un CSV de vraies annonces déjà exportées. Aucun jeu de données fictif n'est utilisé par la console.

## Préparer les données Argus

Copiez `data/argus_prices.example.csv` vers un fichier privé, puis remplacez les lignes par vos valeurs réelles:

```csv
make,model,year,min_price_chf,market_price_chf,max_price_chf
VW,Golf,2018,11000,13500,16000
```

## Utilisation

Recherche en ligne autour de Martigny:

```bash
python -m solanal.deal_finder --argus-csv data/argus_prices.example.csv --radius-km 80 --query "VW Golf" --max-price 18000
```

Analyse hors ligne d'un export d'annonces:

```bash
python -m solanal.deal_finder --argus-csv data/argus_prices.example.csv --listings-csv annonces.csv --min-discount-pct 12 --resale-cost-chf 1500
```

Format attendu pour `annonces.csv`:

```csv
title,price_chf,year,mileage_km,location,url,source,distance_km
VW Golf 1.4 TSI,12000,2018,90000,Martigny,https://example.test/1,manual,5
```

## Interpréter le score

Le rapport affiche:

- le prix de l'annonce;
- le prix de marché Argus;
- la décote en CHF et en pourcentage;
- une marge estimée après frais de revente;
- un score de priorité pour aider à contacter d'abord les vendeurs les plus intéressants.

Avant achat, vérifiez toujours l'historique d'entretien, les frais MFK, les pneus, les sinistres, les garanties, la TVA éventuelle et la liquidité réelle du modèle.
