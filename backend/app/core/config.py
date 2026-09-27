"""app/core/config.py  —  CORREGIDO

Cambios:
 - Falla al arrancar si ENVIRONMENT=production y SECRET_KEY es la de ejemplo o corta.
 - Falla si en produccion CORS = '*' ('*' + allow_credentials=True lo rechaza el navegador).
 - BACKEND_CORS_ORIGINS acepta lista separada por comas ("https://a.com,https://b.com").
 - Respeta DATABASE_URL del entorno (docker-compose ya la mandaba y se ignoraba).
 - TRUSTED_PROXY_HOPS para resolver la IP real detras de Traefik/nginx.
"""
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRETS = {
    "supersecretkeychangeinproduction",
    "cambiar-esto-en-produccion-por-algo-seguro",
    "genera_una_cadena_larga_y_aleatoria_aqui",
    "",
}


class Settings(BaseSettings):
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "mijornada"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Si el entorno define DATABASE_URL (docker-compose lo hace), tiene prioridad.
    DATABASE_URL_OVERRIDE: str = Field(default="", validation_alias="DATABASE_URL")

    SECRET_KEY: str = "supersecretkeychangeinproduction"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    TIMEZONE: str = "America/Monterrey"
    ENVIRONMENT: str = "development"
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    # Saltos de proxy entre el cliente y el backend (Traefik=1, Traefik+nginx=2).
    TRUSTED_PROXY_HOPS: int = 2

    ULTRAMSG_INSTANCE: str = ""
    ULTRAMSG_TOKEN: str = ""
    REMINDERS_ENABLED: bool = False
    ATTENDANCE_START_DATE: str = ""
    APP_URL: str = "https://myjornada.pleg.com.mx"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_SECURITY: str = "SSL"
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_FROM_NAME: str = "GRUPO EXPO - Recursos Humanos"

    WEBHOOK_CHECK_IN_URL: str = ""
    WEBHOOK_CHECK_OUT_URL: str = ""
    WEBHOOK_TASK_COMPLETED_URL: str = ""

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _validate_production(self):
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY.strip("\"'") in INSECURE_SECRETS or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY inseguro en produccion. Genera uno con: "
                    "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("BACKEND_CORS_ORIGINS no puede ser '*' en produccion.")
        return self

    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
