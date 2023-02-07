import asyncio
import configparser
import json
import logging as log
import os
import sys
from datetime import datetime

import discord
import httplib2
import redis
from discord import app_commands
from googleapiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

from constant import (ACTIVE, CLIENT_SECRETS_FILE, COMMAND_LEAVE,
                      COMMAND_START, COMMAND_STOP, LIVE,
                      MISSING_CLIENT_SECRETS_MESSAGE, REDIS_CHAT_KEY,
                      REDIS_STATUS_KEY, YOUTUBE_API_SERVICE_NAME,
                      YOUTUBE_API_VERSION, YOUTUBE_READ_WRITE_SCOPE)
from util import write_to_file

os.path.abspath(os.path.join(os.path.dirname(
    __file__), CLIENT_SECRETS_FILE))

log.basicConfig(
    level=log.DEBUG,
    format='%(asctime)s|%(name)s|%(levelname)s|%(message)s',
    datefmt='%d-%b-%y %H:%M:%S'
)


def config_setup():
    log.info("loading config...")
    global client_secret_raw, redis_host, redis_port, discord_token, bot_channel_name, authorized_user

    config = configparser.RawConfigParser()
    config.read(r'./config.txt')
    redis_host = config.get('app', 'redis_host')
    redis_port = config.get('app', 'redis_port')
    discord_token = config.get('app', 'discord_token')
    bot_channel_name = config.get('app', 'bot_channel_name')
    authorized_user = config.get('app', 'authorized_user')

    client_secret_raw = config.get('app', 'client_secrets_json')
    client_secret_json = json.loads(client_secret_raw)
    write_to_file(CLIENT_SECRETS_FILE, client_secret_json)
    log.info("config loaded")


def redis_setup():
    log.info("setup redis...")
    global r
    r = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=0,
        connection_pool=None
    )
    try:
        if r.ping():
            log.info("Ping redis success")
        else:
            log.info("Ping redis failed")
    except Exception as e:
        log.error("Ping redis failed, err: "+str(e))
        sys.exit()


def get_authenticated_service(args):
    flow = flow_from_clientsecrets(
        CLIENT_SECRETS_FILE,
        scope=YOUTUBE_READ_WRITE_SCOPE,
        message=MISSING_CLIENT_SECRETS_MESSAGE
    )

    storage = Storage("%s-oauth2.json" % sys.argv[0])
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, args)

    return build(
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        http=credentials.authorize(httplib2.Http())
    )


def authenticate_youtube():
    global youtube
    args = argparser.parse_args()
    youtube = get_authenticated_service(args)


def search_live_stream(channel_id):
    search_result = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=5,
        order="date",
    ).execute()
    write_to_file("python_output.json", search_result)
    for l in search_result["items"]:
        if l["snippet"]["liveBroadcastContent"] == LIVE:
            live_stream_id = l["id"]["videoId"]
            live_stream_title = l["snippet"]["title"]
            channel_name = l["snippet"]["channelTitle"]
            return [live_stream_id, live_stream_title, channel_name]
    return []


def get_live_chat_id(live_stream_id):
    live_stream_result = youtube.videos().list(
        part="snippet,contentDetails,liveStreamingDetails",
        id=live_stream_id,
    ).execute()
    write_to_file("python_output2.json", live_stream_result)
    livechat_id = live_stream_result["items"][0]["liveStreamingDetails"]["activeLiveChatId"]
    return livechat_id


def get_live_chat_data(live_chat_id):
    live_chat_result = youtube.liveChatMessages().list(
        part="snippet,authorDetails",
        liveChatId=live_chat_id,
        maxResults=2000
    ).execute()
    write_to_file("python_output3.json", live_chat_result)
    return live_chat_result["items"]


def redis_is_exist(key: str) -> bool:
    return r.exists(key)


def redis_set(key: str, v: str):
    r.set(key, v)


def redis_get(key: str) -> str | None:
    r.get(key)


def redis_del(key: str):
    for k in r.scan_iter(key):
        r.delete(k)


async def relay_chat(display_name: str, channel_id: str, live_stream_id: str, thread: discord.Thread):
    if not live_stream_id:
        log.error("no live stream id")
    else:
        live_chat_id = get_live_chat_id(live_stream_id)
        if not live_chat_id:
            log.error("something wrong, I dont get any livechatID huh!?!?!?")
        else:
            log.debug("got live chat data, channel_id: {}, live_chat_id: {}".format(
                channel_id, live_chat_id))
            chat_redis_key = REDIS_CHAT_KEY.format(
                channel_id, live_chat_id, display_name)

            while True:
                if not redis_is_exist(REDIS_STATUS_KEY.format(channel_id)):
                    break

                chats = get_live_chat_data(live_chat_id)
                for c in chats:
                    if c["authorDetails"]["displayName"] == display_name:
                        redis_key = chat_redis_key+c["id"]
                        if not redis_is_exist(redis_key):
                            msg = c["snippet"]["displayMessage"]
                            redis_set(redis_key, msg)
                            await thread.send(content="**__{}__: {}**".format(display_name, msg))

                await asyncio.sleep(10)  # sleep for 10 seconds


def discord_setup():
    global guild_id
    log.info("setup discord...")

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    guild_id = discord.Object(id=1071483470141997056)

    @client.event
    async def on_ready():
        await tree.sync(guild=guild_id)
        log.info(f'{client.user} has connected to Discord!')

    @tree.command(name=COMMAND_START, description="Start relaying live chat", guild=guild_id)
    async def start_command(interaction: discord.Interaction, channel_id: str, author_name: str):
        if redis_is_exist(REDIS_STATUS_KEY.format(channel_id)):
            await interaction.response.send_message("relaying for channel {} already started".format(channel_id))
            return

        # await interaction.response.send_message("Start relaying {}, please check the newly created thread for this live stream".format(channel_name))
        await interaction.response.send_message("Start relaying...")

        g = client.get_guild(interaction.guild.id)
        tc = None
        for c in g.text_channels:
            if c.name == bot_channel_name:
                tc = c
        if tc is None:
            await interaction.followup.send("Text channel for relaying live chat is not found")
            return

        live_stream_data = search_live_stream(channel_id)
        if len(live_stream_data) < 1:
            await interaction.followup.send("channel {} is not live streaming right now".format(channel_id))
            return

        redis_set(REDIS_STATUS_KEY.format(
            channel_id), ACTIVE)

        live_stream_id = live_stream_data[0]
        live_stream_title = live_stream_data[1]
        channel_name = live_stream_data[2]

        log.debug("got live stream data, channel name: {}, live stream id: {}, live stream title: {}".format(
            channel_name, live_stream_id, live_stream_title))

        log.info(
            "creating new thread for livechat relay, channel: {}".format(channel_id))
        thread_name = "{}|{}|{}".format(
            datetime.today().strftime('%Y-%m-%d'), channel_name, live_stream_title)
        if len(thread_name) > 100:
            thread_name = thread_name[:100]
        thread = await tc.create_thread(name=thread_name, reason="livechat relay", type=discord.ChannelType.public_thread)
        log.debug("thread id: {}, name: {}".format(
            thread.id, thread.name))
        await thread.send(content="This is the start of this thread, relaying livechat...")
        await thread.send(content="@everyone")

        await relay_chat(
            display_name=author_name,
            channel_id=channel_id,
            live_stream_id=live_stream_id,
            thread=thread
        )

    @tree.command(name=COMMAND_STOP, description="Stoping live chat relay", guild=guild_id)
    async def stop_command(interaction: discord.Interaction, channel_id: str):
        redis_del("{}::*".format(channel_id))
        await interaction.response.send_message("Stop relaying livechat for channel {}".format(channel_id))
        log.info(
            "stop relaying livechat for channel: {}".format(channel_id))

    @tree.command(name=COMMAND_LEAVE, description="Make bot leaves the server", guild=guild_id)
    async def leave_command(interaction: discord.Integration):
        await interaction.response.send_message("Bye bye! May we meet again somewhere")
        print(f"leaving server {interaction.guild.id}")
        await client.get_guild(interaction.guild.id).leave()

    client.run(discord_token)


if __name__ == "__main__":
    log.info("starting bot...")
    authenticate_youtube()
    config_setup()
    redis_setup()
    discord_setup()
