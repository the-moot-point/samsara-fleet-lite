from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

API_TOKEN = os.getenv("SAMSARA_API_TOKEN")
ORG_ID = os.getenv("SAMSARA_ORG_ID")
PAYCOM_DIR = Path(os.getenv("PAYCOM_DIR", "data"))
LOG_FILE = Path(os.getenv("LOG_FILE", "driver_sync.log"))
REQUEST_TIMEOUT = 10
BATCH_SIZE = 40  # 40 × 1.5 s sleeps stays under 100 req/min
