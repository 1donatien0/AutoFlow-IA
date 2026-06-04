from app.services.integrations.common import IntegrationError
from app.services.integrations.gmail import (
    connect_gmail_demo,
    get_gmail_auth_url,
    handle_gmail_callback,
    sync_gmail_messages,
)
from app.services.integrations.outlook import (
    connect_outlook_demo,
    get_outlook_auth_url,
    handle_outlook_callback,
    sync_outlook_messages,
)

__all__ = [
    "IntegrationError",
    "connect_gmail_demo",
    "get_gmail_auth_url",
    "handle_gmail_callback",
    "sync_gmail_messages",
    "connect_outlook_demo",
    "get_outlook_auth_url",
    "handle_outlook_callback",
    "sync_outlook_messages",
]
