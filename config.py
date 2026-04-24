import os
import secrets


def load_local_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip().lstrip("\ufeff")
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ[key] = value


load_local_env()

# Persist a stable secret key in .secret_key file if not set via env
def _get_or_create_secret_key():
    env_key = os.getenv("SECRET_KEY", "").strip()
    if env_key and env_key != "your_secret_key_here":
        return env_key
    key_file = os.path.join(os.path.dirname(__file__), ".secret_key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            stored = f.read().strip()
            if stored:
                return stored
    new_key = secrets.token_hex(32)
    with open(key_file, "w") as f:
        f.write(new_key)
    return new_key


class Config:
    SECRET_KEY = _get_or_create_secret_key()
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "Dattu@1234")
    DB_NAME = os.getenv("DB_NAME", "canteen_db")
    DB_SSL_DISABLED = os.getenv("DB_SSL_DISABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    DB_CONNECTION_TIMEOUT = int(os.getenv("DB_CONNECTION_TIMEOUT", "10"))
    AUTO_DB_SETUP = os.getenv("AUTO_DB_SETUP", "true").strip().lower() in {"1", "true", "yes", "on"}