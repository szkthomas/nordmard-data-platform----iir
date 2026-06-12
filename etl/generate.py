"""Szintetikus, mégis koherens kiskereskedelmi adat generálása.

A termék- és ügyfél-törzs determinisztikus (SEED), a rendelés-batch viszont
ciklusonként friss (valós idejű beáramlás szimulálása a dashboardokhoz).
"""
import random
import itertools
from datetime import datetime, timezone, timedelta

import config

# Kategória -> jellemző márkák
CATEGORIES = {
    "Electronics": ["Nordics", "Volt", "PixelPlus"],
    "Home":        ["Hygge", "NestCo"],
    "Sports":      ["Fjord", "Apex"],
    "Beauty":      ["Lumen", "Aura"],
    "Grocery":     ["DailyFresh", "GreenLeaf"],
    "Toys":        ["PlayMore", "TinkerKid"],
}

COUNTRIES = [
    ("Hungary", "Budapest"), ("Hungary", "Debrecen"), ("Hungary", "Szeged"),
    ("Germany", "Berlin"),   ("Germany", "Munich"),
    ("Austria", "Vienna"),   ("Romania", "Cluj-Napoca"), ("Romania", "Bucharest"),
    ("Poland", "Warsaw"),    ("Czechia", "Prague"),      ("Slovakia", "Bratislava"),
]

SEGMENTS = ["Consumer", "SMB", "Enterprise"]
CHANNELS = ["web", "mobile", "store", "partner"]

FIRST_NAMES = ["Anna", "Bence", "Csaba", "Dora", "Eszter", "Ferenc", "Gabor",
               "Hanna", "Imre", "Julia", "Klara", "Levente", "Mark", "Nora",
               "Oliver", "Petra", "Robert", "Sara", "Tamas", "Vera"]
LAST_NAMES = ["Nagy", "Kovacs", "Toth", "Szabo", "Horvath", "Varga", "Kiss",
              "Molnar", "Nemeth", "Farkas", "Balogh", "Papp"]


def build_products() -> list:
    """Determinisztikus termékkatalógus (kategóriánként 6 termék)."""
    rng = random.Random(config.SEED)
    products, pid = [], 1000
    for category, brands in CATEGORIES.items():
        for n in range(6):
            brand = rng.choice(brands)
            cost = round(rng.uniform(3.0, 400.0), 2)
            price = round(cost * rng.uniform(1.25, 2.40), 2)
            products.append({
                "product_id": pid,
                "product_name": f"{brand} {category[:3].upper()}-{n + 1:02d}",
                "category": category,
                "brand": brand,
                "unit_cost": cost,
                "list_price": price,
            })
            pid += 1
    return products


def build_customers(n: int) -> list:
    """Determinisztikus ügyfél-törzs."""
    rng = random.Random(config.SEED + 1)
    now = datetime.now(timezone.utc)
    customers = []
    for cid in range(1, n + 1):
        country, city = rng.choice(COUNTRIES)
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        signup = (now - timedelta(days=rng.randint(1, 1200))).date()
        customers.append({
            "customer_id": cid,
            "full_name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}{cid}@example.com",
            "country": country,
            "city": city,
            "segment": rng.choices(SEGMENTS, weights=[6, 3, 1])[0],
            "signup_date": signup,
        })
    return customers


# Globális, monoton növő rendelésazonosító (időbélyeg-alapú kezdőérték)
_order_seq = itertools.count(int(datetime.now(timezone.utc).timestamp()) * 1000)


def make_order_batch(products: list, n_customers: int, size: int) -> list:
    """Egy friss rendelés-batch (nem determinisztikus — valós beáramlás szimulációja)."""
    rng = random.Random()
    now = datetime.now(timezone.utc)
    batch = []
    for _ in range(size):
        product = rng.choice(products)
        ts = now - timedelta(seconds=rng.randint(0, 59))
        batch.append({
            "order_id": next(_order_seq),
            "order_ts": ts.isoformat(),
            "customer_id": rng.randint(1, n_customers),
            "product_id": product["product_id"],
            "quantity": rng.randint(1, 5),
            "unit_price": product["list_price"],
            # Kedvezmény: legtöbbször 0, néha akciós
            "discount_pct": rng.choice([0, 0, 0, 0, 5, 10, 15, 20]),
            "channel": rng.choices(CHANNELS, weights=[5, 4, 2, 1])[0],
        })
    return batch
