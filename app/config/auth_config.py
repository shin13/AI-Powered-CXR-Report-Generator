# app/config/auth_config.py
import os
from dotenv import load_dotenv
from app.config.config import settings

load_dotenv()

# Authentication settings
AUTH_REQUIRED = True
USERNAME = settings.APP_USERNAME or os.getenv("APP_USERNAME", "admin")
PASSWORD = settings.APP_PASSWORD or os.getenv("APP_PASSWORD", "securepassword")

# JWT settings for token-based auth (for future implementation)
JWT_SECRET = settings.JWT_SECRET or os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 3600  # 1 hour expiration