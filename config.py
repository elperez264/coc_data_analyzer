# python
# File: config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Valor configurable vía variable de entorno DB_PATH; por defecto -> `DB/BetisDB.db`
DB_PATH = os.getenv("DB_PATH", os.path.abspath(os.path.join(BASE_DIR, "DB", "BetisDB.db")))

# Asegurar que la carpeta que contendrá la BD existe
_db_dir = os.path.dirname(DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)