import pickle
import hashlib
from pathlib import Path

CACHE_DIR = Path("/tmp/app_cache")


def cache_key(name):
    return hashlib.sha256(name.encode()).hexdigest()


def load_from_cache(name):
    path = CACHE_DIR / cache_key(name)
    if path.exists():
        data = path.read_bytes()
        return pickle.loads(data)
    return None


def save_to_cache(name, obj):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / cache_key(name)
    path.write_bytes(pickle.dumps(obj))
