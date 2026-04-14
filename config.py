from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'game.db'}")
