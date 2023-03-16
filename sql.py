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
        self._db = db

    def add_channel(self, channel_id: str, channel_title: str, channel_custom_url: str):
        self._logger.info(
            f"Add new channel, id: {channel_id}, title: {channel_title}, custom url: {channel_custom_url}")
        sql = "INSERT INTO channels (yt_id, name, custom_url) VALUES (%s, %s, %s)"
        val = (channel_id, channel_title, channel_custom_url)
        cursor = self._db.cursor()
        cursor.execute(sql, val)
        self._db.commit()

    def is_channel_exist(self, channel_id: str) -> bool:
        self._logger.info(
            f"Checking channel existence, id: {channel_id}")
        sql = f"SELECT EXISTS(SELECT * FROM channels WHERE yt_id = {channel_id})"
        cursor = self._db.cursor()
        cursor.execute(sql)
        return True if cursor.rowcount > 0 else False
