import os
from dotenv import load_dotenv

load_dotenv()

# DhanHQ API Credentials
# Load from environment variables
CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")