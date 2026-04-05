import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENSTATES_API_KEY: str = os.getenv("OPENSTATES_API_KEY", "")
OPENSTATES_BASE_URL: str = "https://v3.openstates.org"
IL_JURISDICTION: str = "ocd-jurisdiction/country:us/state:il/government"
IL_SESSION: str = "2025-2026"

DB_PATH: Path = Path(__file__).parent / "data" / "tracker.db"

if not OPENSTATES_API_KEY:
    import warnings
    warnings.warn(
        "OPENSTATES_API_KEY is not set. Set it in a .env file to enable live fetching.",
        stacklevel=1,
    )
