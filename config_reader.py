from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    bot_token: SecretStr
    allowed_user_id: int
    db_dsn: str
    redis_host: str
    redis_port: int
    
    model_config = SettingsConfigDict(
        secrets_dir='/run/secrets'
    )

config = Settings()

