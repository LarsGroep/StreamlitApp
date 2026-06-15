import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://lofi:lofi@localhost:5432/lofi")

SCRAPER_DATA_DIR: Path = Path(
    os.getenv("SCRAPER_DATA_DIR", str(Path(__file__).parent.parent / "ra-scraper-master" / "scraper"))
)

LASTFM_API_KEY: str = os.getenv("LASTFM_API_KEY", "")
CHARTMETRIC_API_KEY: str = os.getenv("CHARTMETRIC_API_KEY", "")
CHARTMETRIC_REFRESH_TOKEN: str = os.getenv("CHARTMETRIC_REFRESH_TOKEN", "")

RESOLUTION_CONFIDENCE_THRESHOLD: float = 0.85
MAINSTREAM_LISTENER_THRESHOLD: int = 1_500_000
