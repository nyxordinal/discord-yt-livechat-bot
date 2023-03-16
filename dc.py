import asyncio
import logging as log
from datetime import datetime

import discord
from discord import app_commands

from config import Config
from constant import (ACTIVE, COMMAND_CHANNEL_ADD, COMMAND_LEAVE,
                      COMMAND_START, COMMAND_STOP, REDIS_CHAT_KEY,
                      REDIS_STATUS_KEY)
from rd import Redis
from sql import MysqlClient
from yt import YoutubeClient


class DiscordClient:
    def __init__(self, logger: log, config: Config, guild_id: int, redis: Redis, youtube: YoutubeClient, mysql: MysqlClient) -> None:
        self._logger = logger
        self._config = config
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        self._tree = app_commands.CommandTree(self._client)
        self._guild_id = discord.Object(id=guild_id)
        self._yt = youtube
        self._rd = redis
        self._db = mysql

    def get_guild_id(self) -> discord.Object:
        return self._guild_id

    def run_discord(self):
        @self._client.event
        async def on_ready():
            await self._tree.sync(guild=self._guild_id)
            self._logger.info(f'{self._client.user} has connected to Discord!')

        @self._tree.command(name=COMMAND_START, description="Start relaying live chat", guild=self._guild_id)
        async def start_command(interaction: discord.Interaction, channel_id: str, author_name: str):
            if self._rd.is_exist(REDIS_STATUS_KEY.format(channel_id)):
                await interaction.response.send_message(f"relaying for channel {channel_id} already started")
                return

            await interaction.response.send_message("Start relaying...")
            self._logger.info(f"start relaying channel: {channel_id}")

            g = self._client.get_guild(interaction.guild.id)
            tc = None
            for c in g.text_channels:
                if c.name == self._config.bot_channel_name:
                    tc = c
            if tc is None:
                await interaction.followup.send("Text channel for relaying live chat is not found")
                return

            live_stream_data = self._yt.search_live_stream(channel_id)
            if len(live_stream_data) < 1:
                await interaction.followup.send(f"channel {channel_id} is not live streaming right now")
                return

            self._rd.set(REDIS_STATUS_KEY.format(
                channel_id), ACTIVE)

            live_stream_id = live_stream_data[0]
            live_stream_title = live_stream_data[1]
            channel_name = live_stream_data[2]

            self._logger.debug(
                f"got live stream data, channel name: {channel_name}, live stream id: {live_stream_id}, live stream title: {live_stream_title}")

            thread = await self._create_thread(tc=tc, channel_id=channel_id, channel_name=channel_name, live_stream_title=live_stream_title)

            await self._relay_chat(
                author_name=author_name,
                channel_id=channel_id,
                live_stream_id=live_stream_id,
                thread=thread
            )

        @self._tree.command(name=COMMAND_STOP, description="Stoping live chat relay", guild=self._guild_id)
        async def stop_command(interaction: discord.Interaction, channel_id: str):
            self._rd.delete(f"{channel_id}::*")
            await interaction.response.send_message(f"Stop relaying livechat for channel {channel_id}")
            self._logger.info(
                f"stop relaying livechat for channel: {channel_id}")

        @self._tree.command(name=COMMAND_LEAVE, description="Make bot leaves the server", guild=self._guild_id)
        async def leave_command(interaction: discord.Interaction):
            await interaction.response.send_message("Bye bye! May we meet again somewhere")
            print(f"leaving server {interaction.guild.id}")
            await self._client.get_guild(interaction.guild.id).leave()

        @self._tree.command(name=COMMAND_CHANNEL_ADD, description="Add new channel to bot, only useable by admin", guild=self._guild_id)
        async def add_channel(interaction: discord.Interaction, channel_id: str):
            user_tag = f"{interaction.user.name}#{interaction.user.discriminator}"
            if user_tag == self._config.admin_user:
                await interaction.response.send_message(f"Adding new channel command requested by {interaction.user.name}")
                if self._db.is_channel_exist(channel_id):
                    await interaction.followup.send("Channel already exist")
                    return
                channel_data = self._yt.get_channel_data(channel_id=channel_id)
                self._db.add_channel(
                    channel_id=channel_data[0],
                    channel_title=channel_data[1],
                    channel_custom_url=channel_data[2]
                )
                await interaction.followup.send(f"Channel id: {channel_data[0]}, title: {channel_data[1]} added successfully")
            else:
                await interaction.response.send_message("You don't have access to this command")

        self._client.run(self._config.discord_token)

    async def _create_thread(self, tc: discord.TextChannel, channel_id: str, channel_name: str, live_stream_title: str) -> discord.Thread:
        self._logger.info(
            f"creating new thread for livechat relay, channel: {channel_id}")
        thread_name = f"{datetime.today().strftime('%Y-%m-%d')}|{channel_name}|{live_stream_title}"
        if len(thread_name) > 100:
            thread_name = thread_name[:100]
        thread = await tc.create_thread(name=thread_name, reason="livechat relay", type=discord.ChannelType.public_thread)
        self._logger.debug(f"thread id: {thread.id}, name: {thread.name}")
        await thread.send(content="This is the start of this thread, relaying livechat...")
        await thread.send(content="@everyone")
        return thread

    async def _relay_chat(self, author_name: str, channel_id: str, live_stream_id: str, thread: discord.Thread):
        if not live_stream_id:
            self._logger.error("no live stream id")
        else:
            live_chat_id = self._yt.get_live_chat_id(
                live_stream_id=live_stream_id)
            self._yt.get_live_chat_id(live_stream_id)
            if not live_chat_id:
                self._logger.error(
                    "something wrong, I dont get any livechatID huh!?!?!?")
            else:
                self._logger.debug(
                    f"got live chat data, channel_id: {channel_id}, live_chat_id: {live_chat_id}")
                chat_redis_key = REDIS_CHAT_KEY.format(
                    channel_id, live_chat_id, author_name)

                while True:
                    if not self._rd.is_exist(REDIS_STATUS_KEY.format(channel_id)):
                        break

                    chats = self._yt.get_live_chat_data(live_chat_id)
                    for c in chats:
                        if c["authorDetails"]["displayName"] == author_name:
                            redis_key = chat_redis_key+c["id"]
                            if not self._rd.is_exist(redis_key):
                                msg = c["snippet"]["displayMessage"]
                                self._rd.set(redis_key, msg)
                                await thread.send(content=f"**__{author_name}__: {msg}**")

                    await asyncio.sleep(10)  # sleep for 10 seconds
