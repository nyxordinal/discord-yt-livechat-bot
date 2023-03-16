import json
import os

from constant import CLIENT_SECRETS_FILE
from util import write_to_file


class Config:
    def __init__(self) -> None:
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = os.getenv("REDIS_PORT", "6379")
        self.discord_token = os.getenv("DISCORD_TOKEN", "")
        self.bot_channel_name = os.getenv("BOT_CHANNEL_NAME", "")
        self.admin_user = os.getenv("ADMIN_USER", "")

        client_secret_raw = os.getenv("CLIENT_SECRETS_JSON", "")
        client_secret_json = json.loads(client_secret_raw)
        write_to_file(CLIENT_SECRETS_FILE, client_secret_json)
