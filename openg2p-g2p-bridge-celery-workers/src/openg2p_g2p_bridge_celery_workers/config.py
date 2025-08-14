from openg2p_g2p_bridge_bank_connectors.config import Settings as BankConnectorSettings
from openg2p_g2pconnect_mapper_lib.config import Settings as BaseSettings
from pydantic_settings import SettingsConfigDict

from . import __version__


class Settings(BankConnectorSettings, BaseSettings):
    model_config = SettingsConfigDict(env_prefix="g2p_bridge_celery_workers_", env_file=".env", extra="allow")
    openapi_title: str = "OpenG2P G2P Bridge Celery Workers"
    openapi_description: str = """
        Celery workers for OpenG2P G2P Bridge API
        ***********************************
        Further details goes here
        ***********************************
        """
    openapi_version: str = __version__

    db_dbname: str = "openg2p_g2p_bridge_db"
    db_driver: str = "postgresql"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_backend_url: str = "redis://localhost:6379/0"

    bank_fa_deconstruct_strategy: str = (
        r"^account_number:(?P<account_number>.*)"
        r"\.branch_code:(?P<branch_code>.*)"
        r"\.bank_code:(?P<bank_code>.*)"
        r"\.mobile_number:(?P<mobile_number>.*)"
        r"\.email_address:(?P<email_address>.*)"
        r"\.fa_type:(?P<fa_type>.*)$"
    )
    mobile_wallet_deconstruct_strategy: str = (
        r"^mobile_number:(?P<mobile_number>.*)"
        r"\.wallet_provider_name:(?P<wallet_provider_name>.*)"
        r"\.wallet_provider_code:(?P<wallet_provider_code>.*)"
        r"\.fa_type:(?P<fa_type>.*)$"
    )
    email_wallet_deconstruct_strategy: str = (
        r"^email_address:(?P<email_address>.*)"
        r"\.wallet_provider_name:(?P<wallet_provider_name>.*)"
        r"\.wallet_provider_code:(?P<wallet_provider_code>.*)"
        r"\.fa_type:(?P<fa_type>.*)$"
    )

    mapper_request_sender_id: str = "openg2p-g2p-bridge"
