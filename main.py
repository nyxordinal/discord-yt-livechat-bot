import asyncio
import configparser
import json
import os
import sys
from datetime import datetime

import discord
import httplib2
import redis
from googleapiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

from constant import (ACTIVE, CLIENT_SECRETS_FILE, COMMAND_START, COMMAND_STOP,
                      LIVE, MISSING_CLIENT_SECRETS_MESSAGE, REDIS_CHAT_KEY,
                      REDIS_LIVECHAT_KEY, REDIS_STATUS_KEY,
                      YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                      YOUTUBE_READ_WRITE_SCOPE)
from util import get_command, write_to_file

os.path.abspath(os.path.join(os.path.dirname(
    __file__), CLIENT_SECRETS_FILE))


def config_setup():
    print("loading config...")
    global client_secret_raw, redis_host, redis_port, discord_token, bot_channel_name

    config = configparser.RawConfigParser()
    config_file_path = r'./config.txt'
    config.read(config_file_path)
    redis_host = config.get('app', 'redis_host')
    redis_port = config.get('app', 'redis_port')
    discord_token = config.get('app', 'discord_token')
    bot_channel_name = config.get('app', 'bot_channel_name')

    client_secret_raw = config.get('app', 'client_secrets_json')
    client_secret_json = json.loads(client_secret_raw)
    write_to_file(CLIENT_SECRETS_FILE, client_secret_json)
    print("config loaded")


def redis_setup():
    print("setup redis...")
    global r
    r = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=0,
        connection_pool=None
    )
    try:
        if r.ping():
            print("Ping redis success")
        else:
            print("Ping redis failed")
    except Exception as e:
        print("Ping redis failed, err: "+str(e))
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
            livestream_id = l["id"]["videoId"]
            channel_name = l["snippet"]["channelTitle"]
            print("they are streaming, channel name: {}, livestream id: {}".format(
                channel_name, livestream_id))
            return [livestream_id, channel_name]
    return []


def get_live_chat_id(livestream_id):
    livestream_result = youtube.videos().list(
        part="snippet,contentDetails,liveStreamingDetails",
        id=livestream_id,
    ).execute()
    write_to_file("python_output2.json", livestream_result)
    livechat_id = livestream_result["items"][0]["liveStreamingDetails"]["activeLiveChatId"]
    print("got livechat ID, livechatID: "+livechat_id)
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
        print("no live stream for today")
    else:
        live_chat_id = get_live_chat_id(live_stream_id)
        if not live_chat_id:
            print("something wrong, I dont get any livechatID huh!???")
        else:
            print("got live chat data")
            redis_set(REDIS_LIVECHAT_KEY.format(
                channel_id), live_chat_id)
            chat_redis_key = REDIS_CHAT_KEY.format(
                channel_id, live_chat_id, display_name)

            while True:
                if not redis_is_exist(REDIS_STATUS_KEY.format(channel_id)):
                    print("stopping the relaying now")
                    break

                chats = get_live_chat_data(live_chat_id)
                for c in chats:
                    if c["authorDetails"]["displayName"] == display_name:
                        redis_key = chat_redis_key+c["id"]
                        if not redis_is_exist(redis_key):
                            # save to redis
                            msg = c["snippet"]["displayMessage"]
                            redis_set(
                                redis_key, msg)
                            print("chat ID: "+c["id"])
                            print(msg)

                            # relay to discord
                            await thread.send(content="**__{}__: {}**".format(display_name, msg))

                print("sleep for 10 seconds")
                await asyncio.sleep(10)


def discord_setup():
    print("setup discord...")

    intent = discord.Intents.default()
    intent.message_content = True

    client = discord.Client(intents=intent)

    @client.event
    async def on_ready():
        print(f'{client.user} has connected to Discord!')

    @client.event
    async def on_message(message: discord.Message):
        if message.author.name == 'nyxordinal':
            print("got message from nyxordinal")

            if message.content.startswith("/dytb"):
                commands = get_command(message.content)

                if len(commands) < 2:
                    return

                if commands[0] == COMMAND_START:
                    channel_id = commands[1]
                    author_name = commands[2]

                    if redis_is_exist(REDIS_STATUS_KEY.format(channel_id)):
                        msg = "relaying for channel {} already started".format(
                            channel_id)
                        print(msg)
                        await message.channel.send(msg)
                        return

                    print("creating new thread")
                    text_channel = client.get_all_channels()
                    tc_id = ""
                    for t in text_channel:
                        if t.name == bot_channel_name:
                            tc_id = t.id
                    tc = client.get_channel(tc_id)

                    live_stream_data = search_live_stream(channel_id)
                    if len(live_stream_data) < 1:
                        print("they are not streaming")
                        return

                    redis_set(REDIS_STATUS_KEY.format(
                        channel_id), ACTIVE)

                    live_stream_id = live_stream_data[0]
                    channel_name = live_stream_data[1]

                    thread_name = "yt-livechat-relay-{}-{}".format(
                        datetime.today().strftime('%Y-%m-%d'), channel_name)
                    thread = await tc.create_thread(name=thread_name, reason="no reason, just bored")
                    print("thread id: {}, name: {}".format(
                        thread.id, thread.name))
                    print("relaying chat...")
                    await thread.send(content="This is the start of this thread, relaying livechat...")
                    await thread.send(content="@everyone")

                    await relay_chat(
                        display_name=author_name,
                        channel_id=channel_id,
                        live_stream_id=live_stream_id,
                        thread=thread
                    )

                elif commands[0] == COMMAND_STOP:
                    channel_id = commands[1]

                    redis_del("{}::*".format(channel_id))
                    await message.channel.send("Stop relaying message for channel {}".format(channel_id))
                    print("stop relaying message...")

            # if message.content == "/bot leave":
            #     for g in client.guilds:
            #         if g.id == message.channel.guild.id:
            #             print("leaving the server ...")
            #             await g.leave()

    client.run(discord_token)


if __name__ == "__main__":
    print("starting bot...")
    authenticate_youtube()
    config_setup()
    redis_setup()
    discord_setup()
