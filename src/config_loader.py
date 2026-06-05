import os
import yaml
from dotenv import load_dotenv

def load_config(config_path="config/config.yaml"):
    """Load pipeline configuration from YAML file."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config

def load_env(env_path="config/.env"):
    """Load environment variables from .env file."""
    load_dotenv(dotenv_path=env_path)

def get_db_credentials():
    """Retrieve database credentials from environment variables."""
    return {
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "name": os.getenv("DB_NAME"),
    }