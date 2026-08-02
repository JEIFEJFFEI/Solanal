from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from html.parser import HTMLParser
from urllib.parse import quote

try:
    import requests
except ImportError:  # pragma: no cover - only needed for live scraping
    requests = None

MARTIGNY_LAT = 46.1028
MARTIGNY_LON = 7.0724
DEFAULT_HEADERS = {
    "User-Agent": "SolanalDealFinder/1.0 (+https://example.invalid; contact owner before production use)",
    "Accept-Language": "fr-CH,fr;q=0.9,en;q=0.7",
}


@dataclass(frozen=True)
class Listing:
    title: str
    price_chf: int
    year: Optional[int]
    mileage_km: Optional[int]
    location: str
    url: str
    source: str = "manual"
    distance_km: Optional[float] = None


@dataclass(frozen=True)
class ArgusValue:
    make: str
    model: str
    year: int
    min_price_chf: int
    market_price_chf: int
    max_price_chf: int


@dataclass(frozen=True)
class DealAssessment:
    listing: Listing
    argus: ArgusValue
    discount_chf: int
    discount_pct: float
    estimated_margin_chf: int
    score: float


def parse_int(text: str) -> Optional[int]:
    digits = re.sub(r"[^0-9]", "", text or "")
    return int(digits) if digits else None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class CsvArgusProvider:
    """Reads market values exported from Argus/Eurotax-style valuation tools.

    Commercial Swiss valuation data is usually licensed, so this provider keeps the
    source explicit: users can export their purchased Argus data to CSV and compare
    listings without hard-coding credentials or scraping protected services.
    """

    def __init__(self, csv_path: Path):
        self.values = self._load(csv_path)

    @staticmethod
    def _load(csv_path: Path) -> list[ArgusValue]:
        rows: list[ArgusValue] = []
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                rows.append(
                    ArgusValue(
                        make=row["make"].strip(),
                        model=row["model"].strip(),
                        year=int(row["year"]),
                        min_price_chf=int(row["min_price_chf"]),
                        market_price_chf=int(row["market_price_chf"]),
                        max_price_chf=int(row["max_price_chf"]),
                    )
                )
        return rows

    def match(self, listing: Listing) -> Optional[ArgusValue]:
        title = listing.title.lower()
        candidates = [v for v in self.values if v.make.lower() in title and v.model.lower() in title]
        if listing.year is not None:
            exact = [v for v in candidates if v.year == listing.year]
            if exact:
                return exact[0]
            candidates.sort(key=lambda v: abs(v.year - listing.year))
        return candidates[0] if candidates else None


class AutoScout24Scraper:
    """Best-effort public listing parser for AutoScout24 Switzerland search pages."""

    BASE_URL = "https://www.autoscout24.ch/fr/s/voiture"

    def __init__(self, session: Optional[requests.Session] = None):
        if requests is None:
            raise RuntimeError("Installez requests (`pip install -r requirements.txt`) pour la recherche en ligne.")
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def search_url(self, radius_km: int, query: str = "", max_price: Optional[int] = None) -> str:
        params = [f"vehtyp=10", "zip=1920", f"r={radius_km}"]
        if query:
            params.append("q=" + quote(query))
        if max_price:
            params.append(f"priceTo={max_price}")
        return self.BASE_URL + "?" + "&".join(params)

    def fetch(self, radius_km: int, query: str = "", max_price: Optional[int] = None) -> list[Listing]:
        response = self.session.get(self.search_url(radius_km, query, max_price), timeout=20)
        response.raise_for_status()
        return parse_autoscout24_html(response.text)


class _CardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: list[dict[str, str]] = []
        self._in_article = False
        self._text: list[str] = []
        self._href = ""
        self._link_text: list[str] = []
        self._in_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attr = dict(attrs)
        if tag == "article":
            self._in_article = True
            self._text = []
            self._href = ""
            self._link_text = []
        if self._in_article and tag == "a" and attr.get("href") and not self._href:
            self._href = attr["href"] or ""
            self._in_link = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._in_link = False
        if tag == "article" and self._in_article:
            self.cards.append({"text": " ".join(self._text), "href": self._href, "title": " ".join(self._link_text)})
            self._in_article = False

    def handle_data(self, data: str) -> None:
        if self._in_article:
            self._text.append(data.strip())
            if self._in_link:
                self._link_text.append(data.strip())


def parse_autoscout24_html(html: str) -> list[Listing]:
    parser = _CardParser()
    parser.feed(html)
    listings: list[Listing] = []
    seen: set[str] = set()
    for card in parser.cards:
        text = " ".join(card["text"].split())
        price_match = re.search(r"CHF\s*([0-9]{1,3}(?:['’.][0-9]{3})+|[0-9]+)", text, re.IGNORECASE)
        if not price_match:
            continue
        url = card["href"]
        if url.startswith("/"):
            url = "https://www.autoscout24.ch" + url
        price = parse_int(price_match.group(1))
        if not price or url in seen:
            continue
        seen.add(url)
        year_match = re.search(r"\b(19[8-9][0-9]|20[0-3][0-9])\b", text)
        mileage_match = re.search(r"([0-9]{1,3}(?:['’.][0-9]{3})+|[0-9]+)\s*km\b", text, re.IGNORECASE)
        listings.append(
            Listing(
                title=card["title"].strip() or text[:80] or "Annonce sans titre",
                price_chf=price,
                year=int(year_match.group(1)) if year_match else None,
                mileage_km=parse_int(mileage_match.group(1)) if mileage_match else None,
                location="Suisse romande / Martigny (selon recherche)",
                url=url,
                source="autoscout24",
            )
        )
    return listings

def load_listings_csv(path: Path) -> list[Listing]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            Listing(
                title=row["title"].strip(),
                price_chf=int(row["price_chf"]),
                year=int(row["year"]) if row.get("year") else None,
                mileage_km=int(row["mileage_km"]) if row.get("mileage_km") else None,
                location=row.get("location", "").strip(),
                url=row.get("url", "").strip(),
                source=row.get("source", "csv").strip() or "csv",
                distance_km=float(row["distance_km"]) if row.get("distance_km") else None,
            )
            for row in csv.DictReader(handle)
        ]


def assess_deals(
    listings: Iterable[Listing],
    provider: CsvArgusProvider,
    min_discount_pct: float = 10.0,
    resale_cost_chf: int = 1200,
) -> list[DealAssessment]:
    deals: list[DealAssessment] = []
    for listing in listings:
        argus = provider.match(listing)
        if not argus:
            continue
        discount = argus.market_price_chf - listing.price_chf
        discount_pct = discount / argus.market_price_chf * 100
        margin = discount - resale_cost_chf
        if discount_pct >= min_discount_pct and margin > 0:
            mileage_penalty = min((listing.mileage_km or 0) / 200_000, 1) * 10
            distance_penalty = min((listing.distance_km or 0) / 100, 1) * 5
            score = discount_pct + (margin / 1000) - mileage_penalty - distance_penalty
            deals.append(DealAssessment(listing, argus, discount, discount_pct, margin, round(score, 2)))
    return sorted(deals, key=lambda d: d.score, reverse=True)


def print_report(deals: Iterable[DealAssessment]) -> None:
    for index, deal in enumerate(deals, start=1):
        l = deal.listing
        print(f"{index}. {l.title}")
        print(f"   Prix annonce: CHF {l.price_chf:,} | Argus marché: CHF {deal.argus.market_price_chf:,}")
        print(f"   Décote: CHF {deal.discount_chf:,} ({deal.discount_pct:.1f}%) | Marge estimée: CHF {deal.estimated_margin_chf:,}")
        print(f"   Année: {l.year or 'n/a'} | km: {l.mileage_km or 'n/a'} | Source: {l.source} | Score: {deal.score}")
        print(f"   {l.url}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repère les annonces auto sous l'Argus autour de Martigny.")
    parser.add_argument("--argus-csv", type=Path, required=True, help="CSV de valeurs Argus/Eurotax exportées légalement")
    parser.add_argument("--listings-csv", type=Path, help="CSV d'annonces à analyser au lieu du scraping")
    parser.add_argument("--radius-km", type=int, default=80, help="Rayon autour de Martigny (1920), par défaut 80 km")
    parser.add_argument("--query", default="", help="Marque/modèle/mots-clés à chercher")
    parser.add_argument("--max-price", type=int, help="Prix maximum CHF pour la recherche en ligne")
    parser.add_argument("--min-discount-pct", type=float, default=10.0, help="Décote minimum vs Argus")
    parser.add_argument("--resale-cost-chf", type=int, default=1200, help="Frais de revente estimés")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    provider = CsvArgusProvider(args.argus_csv)
    listings = load_listings_csv(args.listings_csv) if args.listings_csv else AutoScout24Scraper().fetch(args.radius_km, args.query, args.max_price)
    deals = assess_deals(listings, provider, args.min_discount_pct, args.resale_cost_chf)
    if not deals:
        print("Aucune annonce suffisamment sous le prix Argus n'a été trouvée.")
        return 1
    print_report(deals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
