import logging as log
import os

from dotenv import load_dotenv

from config import Config
from constant import CLIENT_SECRETS_FILE
from dc import DiscordClient
from rd import Redis
from sql import MysqlClient
from yt import YoutubeClient

load_dotenv()
os.path.abspath(os.path.join(os.path.dirname(__file__), CLIENT_SECRETS_FILE))

if __name__ == "__main__":
    log.basicConfig(
        level=log.INFO if os.getenv(
            "ENV", "development") == "production" else log.DEBUG,
        format='%(asctime)s|%(name)s|%(levelname)s|%(message)s',
        datefmt='%d-%b-%y %H:%M:%S'
    )
    logger = log.getLogger()
    logger.info("starting bot...")
    logger.info("loading config...")
    cf = Config()
    logger.info("setup mysql db")
    db = MysqlClient(logger)
    logger.info("setup redis")
    rd = Redis(logger=logger, config=cf)
    logger.info("setup youtube client")
    yt_inst = YoutubeClient()
    logger.info("setup discord client")
    discord = DiscordClient(
        logger=logger,
        config=cf,
        guild_id=1071483470141997056,
        redis=rd,
        youtube=yt_inst,
    )
    discord.run_discord()
