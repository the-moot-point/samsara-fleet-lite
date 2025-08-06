from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

# Samsara API Configuration
API_TOKEN = os.getenv("SAMSARA_BEARER_TOKEN")
if API_TOKEN is None:
    raise EnvironmentError("SAMSARA_BEARER_TOKEN must be set")

# Directory Configuration
PAYCOM_DIR = Path(os.getenv("PAYCOM_DIR", "data"))
LOG_FILE = Path(os.getenv("LOG_FILE", "driver_sync.log"))

# OneDrive Report Directories
HIRES_DIR = Path(
    os.getenv("HIRES_DIR", r"C:\Users\Jonathan\OneDrive - JECOfsb\Flow\Hires")
)
TERMS_DIR = Path(
    os.getenv("TERMS_DIR", r"C:\Users\Jonathan\OneDrive - JECOfsb\Flow\Terms")
)

# Request Configuration
REQUEST_TIMEOUT = 10
BATCH_SIZE = 40  # 40 × 1.5 s sleeps stays under 100 req/min

# Driver Defaults
DEFAULT_PASSWORD = os.getenv("DEFAULT_DRIVER_PASSWORD", "JecoPass123!")


# Create a settings object for easy access
class Settings:
    api_token = API_TOKEN
    paycom_dir = PAYCOM_DIR
    log_file = LOG_FILE
    hires_dir = HIRES_DIR
    terms_dir = TERMS_DIR
    request_timeout = REQUEST_TIMEOUT
    batch_size = BATCH_SIZE
    default_password = DEFAULT_PASSWORD


settings = Settings()
