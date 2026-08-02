from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from solanal.deal_finder import AutoScout24Scraper, CsvArgusProvider, assess_deals, load_listings_csv, print_report

Prompt = Callable[[str], str]


def ask_path(prompt: Prompt, label: str) -> Path:
    while True:
        raw = prompt(label).strip().strip('"')
        path = Path(raw).expanduser()
        if path.exists() and path.is_file():
            return path
        print(f"Fichier introuvable: {path}")


def ask_int(prompt: Prompt, label: str, default: Optional[int] = None) -> Optional[int]:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = prompt(f"{label}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            print("Entrez un nombre entier, ou laissez vide si optionnel.")


def ask_float(prompt: Prompt, label: str, default: float) -> float:
    while True:
        raw = prompt(f"{label} [{default}]: ").strip().replace(",", ".")
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            print("Entrez un nombre, par exemple 12.5.")


def live_search(provider: CsvArgusProvider, prompt: Prompt = input) -> int:
    query = prompt("Marque/modèle à chercher sur AutoScout24 (ex: VW Golf): ").strip()
    radius = ask_int(prompt, "Rayon autour de Martigny en km", 80) or 80
    max_price = ask_int(prompt, "Prix maximum CHF (vide = aucun)")
    min_discount = ask_float(prompt, "Décote minimum vs Argus en %", 10.0)
    resale_cost = ask_int(prompt, "Frais de revente estimés CHF", 1200) or 1200

    print("\nRecherche de vraies annonces en ligne...")
    listings = AutoScout24Scraper().fetch(radius_km=radius, query=query, max_price=max_price)
    print(f"{len(listings)} annonce(s) récupérée(s). Comparaison avec votre fichier Argus...\n")
    deals = assess_deals(listings, provider, min_discount, resale_cost)
    if not deals:
        print("Aucune opportunité selon vos critères. Essayez un rayon plus large ou une décote plus basse.")
        return 1
    print_report(deals)
    return 0


def offline_analysis(provider: CsvArgusProvider, prompt: Prompt = input) -> int:
    listings_path = ask_path(prompt, "Chemin du CSV d'annonces réelles exportées: ")
    min_discount = ask_float(prompt, "Décote minimum vs Argus en %", 10.0)
    resale_cost = ask_int(prompt, "Frais de revente estimés CHF", 1200) or 1200
    deals = assess_deals(load_listings_csv(listings_path), provider, min_discount, resale_cost)
    if not deals:
        print("Aucune opportunité selon vos critères dans ce fichier.")
        return 1
    print_report(deals)
    return 0


def run_console(prompt: Prompt = input) -> int:
    print("=== Solanal Console — test avec données réelles ===")
    print("Cette console n'utilise pas d'exemples fictifs: fournissez vos vraies cotes Argus/Eurotax, puis lancez une recherche live ou importez de vraies annonces.\n")
    argus_path = ask_path(prompt, "Chemin du CSV Argus/Eurotax réel: ")
    provider = CsvArgusProvider(argus_path)

    while True:
        print("\nChoisissez une action:")
        print("1. Chercher de vraies annonces AutoScout24 autour de Martigny")
        print("2. Analyser un CSV de vraies annonces déjà exportées")
        print("3. Quitter")
        choice = prompt("Votre choix [1]: ").strip() or "1"
        if choice == "1":
            return live_search(provider, prompt)
        if choice == "2":
            return offline_analysis(provider, prompt)
        if choice == "3":
            print("À bientôt.")
            return 0
        print("Choix invalide. Tapez 1, 2 ou 3.")


def main() -> int:
    return run_console()


if __name__ == "__main__":
    raise SystemExit(main())
