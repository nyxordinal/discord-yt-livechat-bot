import configparser
import json
import os
import sys
import time

import discord
import httplib2
import redis
from googleapiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

from constant import (CLIENT_SECRETS_FILE, MISSING_CLIENT_SECRETS_MESSAGE,
                      YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                      YOUTUBE_READ_WRITE_SCOPE)
from util import write_to_file

os.path.abspath(os.path.join(os.path.dirname(
    __file__), CLIENT_SECRETS_FILE))


def config_setup():
    print("loading config...")
    global client_secret_raw, redis_host, redis_port, discord_token

    config = configparser.RawConfigParser()
    config_file_path = r'./config.txt'
    config.read(config_file_path)
    redis_host = config.get('app', 'redis_host')
    redis_port = config.get('app', 'redis_port')
    discord_token = config.get('app', 'discord_token')

    client_secret_raw = config.get('app', 'client_secrets_json')
    client_secret_json = json.loads(client_secret_raw)
    write_to_file(CLIENT_SECRETS_FILE, client_secret_json)
    print("config loaded")


def redis_setup():
    print("setup redis...")
    global r
    r = redis.Redis(host=redis_host, port=redis_port, db=0)
    try:
        if r.ping():
            print("Ping redis success")
        else:
            print("Ping redis failed")
    except Exception as e:
        print("Ping redis failed, err: "+str(e))
        sys.exit()


def discord_setup():
    print("setup discord...")
    client = discord.Client()

    @client.event
    async def on_ready():
        print(f'{client.user} has connected to Discord!')

    client.run(discord_token)


def setup_component():
    config_setup()
    redis_setup()
    discord_setup()


def get_authenticated_service(args):
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
                                   scope=YOUTUBE_READ_WRITE_SCOPE,
                                   message=MISSING_CLIENT_SECRETS_MESSAGE)

    storage = Storage("%s-oauth2.json" % sys.argv[0])
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, args)

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                 http=credentials.authorize(httplib2.Http()))


def login():
    global youtube
    args = argparser.parse_args()
    youtube = get_authenticated_service(args)


def search_live_stream(channel_id):
    search_result = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=3,
        order="date",
    ).execute()

    write_to_file("python_output.json", search_result)

    live_broadcast_content = search_result["items"][0]["snippet"]["liveBroadcastContent"]
    if live_broadcast_content == "live":
        livestream_id = search_result["items"][0]["id"]["videoId"]
        channel_name = search_result["items"][0]["snippet"]["channelTitle"]
        print("she is streaming, channel name: {}, livestream id: {}".format(
            channel_name, livestream_id))
        return livestream_id
    else:
        print("she is not streaming")
        return ""


def get_live_chat_id(livestream_id):
    livestream_result = youtube.videos().list(
        part="snippet,contentDetails,liveStreamingDetails",
        id=livestream_id,
    ).execute()

    write_to_file("python_output2.json", livestream_result)

    livechat_id = livestream_result["items"][0]["liveStreamingDetails"]["activeLiveChatId"]
    print("got live chat ID bro, livechatID: "+livechat_id)
    return livechat_id


def get_live_chat_data(live_chat_id):
    live_chat_result = youtube.liveChatMessages().list(
        part="snippet,authorDetails",
        liveChatId=live_chat_id,
        maxResults=2000
    ).execute()

    write_to_file("python_output3.json", live_chat_result)
    return live_chat_result["items"]


def is_exist(key) -> bool:
    return r.exists(key)


def set(key, v):
    r.set(key, v)


def relay_chat(display_name, channel_id):
    live_stream_id = search_live_stream(channel_id)
    if live_stream_id == "":
        print("no live stream for today")
    else:
        live_chat_id = get_live_chat_id(live_stream_id)
        if live_chat_id == "":
            print("something wrong, I dont get any livechatID huh!???")
        else:
            print("get live chat data ...")
            chat_redis_key = live_chat_id+"::"+display_name+"::"

            while True:
                chats = get_live_chat_data(live_chat_id)
                for c in chats:
                    if c["authorDetails"]["displayName"] == display_name:
                        redis_key = chat_redis_key+c["id"]
                        if not is_exist(redis_key):
                            # TODO relay to discord

                            # save to redis
                            set(redis_key, c["snippet"]["displayMessage"])
                            print("chat ID: "+c["id"])
                            print(c["snippet"]["displayMessage"])

                print("sleep for 10 seconds")
                time.sleep(10)


if __name__ == "__main__":
    print("starting bot...")

    setup_component()

    login()

    relay_chat("Nyxordinal", "UCqDN60QQx3GGmfagx1eyIEg")
