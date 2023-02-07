import configparser
import json

from constant import CLIENT_SECRETS_FILE
from util import write_to_file


class Config:
    def __init__(self) -> None:
        config = configparser.RawConfigParser()
        config.read(r'./config.txt')
        self.redis_host = config.get('app', 'redis_host')
        self.redis_port = config.get('app', 'redis_port')
        self.discord_token = config.get('app', 'discord_token')
        self.bot_channel_name = config.get('app', 'bot_channel_name')

        client_secret_raw = config.get('app', 'client_secrets_json')
        client_secret_json = json.loads(client_secret_raw)
        write_to_file(CLIENT_SECRETS_FILE, client_secret_json)
