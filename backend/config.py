import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    finnhub_api_key: str = ""
    polygon_api_key: str = ""
    public_api_key: str = ""
    database_url: str = ""          # PostgreSQL connection string (preferred)
    db_path: str = "../data/trading.db"   # SQLite fallback for local dev
    backend_port: int = 8000

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}


settings = Settings()
