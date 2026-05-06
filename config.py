import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///clickbook.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-dev-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "86400")))
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    CLIENT_URL = os.getenv("CLIENT_URL", "http://localhost:8080")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "25"))
    # Flask-Mail expects real booleans, not truthy strings. Default to TLS on 587,
    # otherwise off (common for local SMTP on port 25).
    _default_tls = MAIL_PORT == 587
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true" if _default_tls else "false").strip().lower() in {"1", "true", "yes", "on"}
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").strip().lower() in {"1", "true", "yes", "on"}
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "no-reply@clickbook.com")



class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

    @classmethod
    def init_app(cls, app):
        required = [
            "SECRET_KEY", "DATABASE_URL", "JWT_SECRET_KEY",
            "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
            "MAIL_SERVER", "MAIL_PORT", "MAIL_USERNAME",
            "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER",
        ]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"Missing required env vars for production: {', '.join(missing)}")
        app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
        app.config["JWT_SECRET_KEY"] = os.environ["JWT_SECRET_KEY"]
        app.config["STRIPE_SECRET_KEY"] = os.environ["STRIPE_SECRET_KEY"]
        app.config["STRIPE_WEBHOOK_SECRET"] = os.environ["STRIPE_WEBHOOK_SECRET"]
        app.config["MAIL_SERVER"] = os.environ["MAIL_SERVER"]
        app.config["MAIL_PORT"] = int(os.environ["MAIL_PORT"])
        app.config["MAIL_USERNAME"] = os.environ["MAIL_USERNAME"]
        app.config["MAIL_PASSWORD"] = os.environ["MAIL_PASSWORD"]
        app.config["MAIL_DEFAULT_SENDER"] = os.environ["MAIL_DEFAULT_SENDER"]



config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
