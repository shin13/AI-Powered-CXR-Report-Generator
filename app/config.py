import os
from typing import List, Union
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Features
    ENABLE_LOGGING: bool = True
    LOG_LEVEL: str = "INFO"

    # API Settings
    BASE_URL: str
    OPENAI_API_KEY: str 
    CHATGPT_MODEL: str = "gpt-4o-mini"

    # CORS and Server Settings
    ALLOWED_ORIGINS: Union[List[str], str] = ["http://localhost"]
    HOST: str = "127.0.0.1"
    PORT: int = 7890
    DEBUG: bool = False

    # Backend Settings
    BACKEND_URL: str

    # AI Service Settings
    BASE_URL_AI: str
    CXR_FEATURES_ENDPOINT: str
    CXR_LINEAR_PROBE_ENDPOINT: str
    AUTH_USERNAME: str
    AUTH_PASSWORD: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    def model_post_init(self, __context):
        """Process values after model initialization"""
        # Convert string ALLOWED_ORIGINS to list if needed
        if isinstance(self.ALLOWED_ORIGINS, str):
            self.ALLOWED_ORIGINS = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

def validate_settings(settings: Settings) -> Settings:
    """Validate that all required settings are present for production use"""
    # Only validate when not in development mode
    if os.getenv("ENVIRONMENT") == "production":
        missing = []
        
        # Validate essential settings for production
        if not settings.OPENAI_API_KEY or "your-openai-key" in settings.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        
        if not settings.BASE_URL_AI or "your-ai-service" in settings.BASE_URL_AI:
            missing.append("BASE_URL_AI")
            
        if not settings.AUTH_USERNAME or settings.AUTH_USERNAME == "your_username":
            missing.append("AUTH_USERNAME")
            
        if not settings.AUTH_PASSWORD or settings.AUTH_PASSWORD == "your_password":
            missing.append("AUTH_PASSWORD")
            
        if settings.DEBUG:
            print("WARNING: DEBUG mode is enabled in production")
            
        if missing:
            raise ValueError(f"Missing required configuration values for production: {', '.join(missing)}")
    
    return settings

# Initialize settings
settings = validate_settings(Settings())