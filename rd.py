import logging as log

import redis

from config import Config


class Redis:
    def __init__(self, logger: log, config: Config) -> None:
        self._logger = logger
        self._r = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=0,
            connection_pool=None
        )

        try:
            if self._r.ping():
                self._logger.info("Ping redis success")
            else:
                self._logger.info("Ping redis failed")
        except Exception as e:
            self._logger.error("Ping redis failed, err: "+str(e))

    def is_exist(self, key: str) -> bool:
        return self._r.exists(key)

    def set(self, key: str, v: str):
        self._r.set(key, v)

    def get(self, key: str) -> str | None:
        self._r.get(key)

    def delete(self, key: str):
        for k in self._r.scan_iter(key):
            self._r.delete(k)
