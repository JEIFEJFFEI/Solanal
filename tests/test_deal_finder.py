from pathlib import Path

from solanal.deal_finder import CsvArgusProvider, Listing, assess_deals, parse_autoscout24_html


def test_assess_deals_ranks_profitable_discount(tmp_path: Path):
    argus = tmp_path / "argus.csv"
    argus.write_text(
        "make,model,year,min_price_chf,market_price_chf,max_price_chf\n"
        "VW,Golf,2018,11000,15000,17000\n",
        encoding="utf-8",
    )
    provider = CsvArgusProvider(argus)
    listings = [
        Listing("VW Golf 1.4 TSI", 12000, 2018, 90000, "Martigny", "https://example.test/1"),
        Listing("VW Golf chère", 14800, 2018, 90000, "Sion", "https://example.test/2"),
    ]

    deals = assess_deals(listings, provider, min_discount_pct=10, resale_cost_chf=1000)

    assert len(deals) == 1
    assert deals[0].discount_chf == 3000
    assert deals[0].estimated_margin_chf == 2000


def test_parse_autoscout24_html_extracts_core_fields():
    html = """
    <article>
      <a href="/fr/d/vw-golf-123">VW Golf 2.0 TDI</a>
      <span>CHF 12'500</span><span>2019</span><span>88'000 km</span>
    </article>
    """

    listings = parse_autoscout24_html(html)

    assert len(listings) == 1
    assert listings[0].price_chf == 12500
    assert listings[0].year == 2019
    assert listings[0].mileage_km == 88000
    assert listings[0].url == "https://www.autoscout24.ch/fr/d/vw-golf-123"
