import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ADMIN_ORIGINS: list[str] = os.getenv("ADMIN_ORIGINS", "*").split(",")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

settings = Settings()