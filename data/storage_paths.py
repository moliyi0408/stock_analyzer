from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_STORE_DIR = PROJECT_ROOT / "datas"
PRICE_CACHE_DIR = DATA_STORE_DIR / "price"
FUNDAMENTAL_CACHE_DIR = DATA_STORE_DIR / "fundamental"
