import os


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


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "Dattu@1234")
    DB_NAME = os.getenv("DB_NAME", "canteen_db")
    AUTO_DB_SETUP = os.getenv("AUTO_DB_SETUP", "true").strip().lower() in {"1", "true", "yes", "on"}