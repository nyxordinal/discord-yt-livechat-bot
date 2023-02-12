import logging as log

import mysql.connector


class MysqlClient:
    def __init__(self, logger: log) -> None:
        db = mysql.connector.connect(
            host="localhost",
            port="13306",
            user="root",
            password="password123",
            database="dc_yt"
        )
        self._logger = logger
        if db.is_connected():
            self._logger.info("MySQL Connection is available")
        else:
            self._logger.info("MySQL Connection is unavailable")
        self._mysql_cursor = db.cursor()
