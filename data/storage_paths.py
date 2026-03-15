from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_STORE_DIR = PROJECT_ROOT / "datas"
PRICE_CACHE_DIR = DATA_STORE_DIR / "price"
FUNDAMENTAL_CACHE_DIR = DATA_STORE_DIR / "fundamental"
CHIP_CACHE_DIR = DATA_STORE_DIR / "chip"
FEATURE_CACHE_DIR = DATA_STORE_DIR / "feature_cache"
TECHNICAL_FEATURE_CACHE_DIR = FEATURE_CACHE_DIR / "technical"
