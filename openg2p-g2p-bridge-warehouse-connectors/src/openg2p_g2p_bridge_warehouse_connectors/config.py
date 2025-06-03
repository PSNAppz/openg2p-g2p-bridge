from openg2p_fastapi_common.config import Settings as BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="g2p_bridge_celery_producers_", env_file=".env", extra="allow"
    )

    db_dbname: str = "openg2p_g2p_bridge_db"
