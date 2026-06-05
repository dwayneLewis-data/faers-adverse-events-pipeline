import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config_loader import load_config, load_env, get_db_credentials


def test_load_config():
    """Verify config.yaml loads and contains expected top-level keys."""
    config = load_config()
    assert "api" in config
    assert "data" in config
    assert "logging" in config
    assert "database" in config
    print("test_load_config passed")


def test_load_env_and_credentials():
    """.env loads and credentials are retrievable."""
    load_env()
    creds = get_db_credentials()
    assert creds["user"] is not None
    assert creds["password"] is not None
    assert creds["host"] is not None
    assert creds["port"] is not None
    assert creds["name"] is not None
    print("test_load_env_and_credentials passed")


if __name__ == "__main__":
    test_load_config()
    test_load_env_and_credentials()
    print("All config_loader tests passed")
