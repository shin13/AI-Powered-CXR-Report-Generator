from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BASE_URL: str
    OPENAI_API_KEY: str 
    CHATGPT_MODEL: str = "gpt-4o-mini"
    ALLOWED_ORIGINS: list = ["http://localhost"]
    HOST: str = "127.0.0.1"
    PORT: int = 7890
    DEBUG: bool = True
    USERNAME: str
    PASSWORD: str
    BACKEND_URL: str
    BASE_URL_AI: str
    CXR_FEATURES_ENDPOINT: str
    CXR_LINEAR_PROBE_ENDPOINT: str
    AUTH_USERNAME: str
    AUTH_PASSWORD: str

    class Config:
        env_file = ".env"

settings = Settings()