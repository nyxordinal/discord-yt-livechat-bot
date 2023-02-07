import sys
from typing import List

import httplib2
from googleapiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow

from constant import (CLIENT_SECRETS_FILE, LIVE,
                      MISSING_CLIENT_SECRETS_MESSAGE, YOUTUBE_API_SERVICE_NAME,
                      YOUTUBE_API_VERSION, YOUTUBE_READ_WRITE_SCOPE)
from util import write_to_file


class YoutubeClient:
    def __init__(self) -> None:
        flow = flow_from_clientsecrets(
            CLIENT_SECRETS_FILE,
            scope=YOUTUBE_READ_WRITE_SCOPE,
            message=MISSING_CLIENT_SECRETS_MESSAGE
        )
        storage = Storage("%s-oauth2.json" % sys.argv[0])
        credentials = storage.get()
        if credentials is None or credentials.invalid:
            credentials = run_flow(flow, storage)
        self._yt_inst = build(
            YOUTUBE_API_SERVICE_NAME,
            YOUTUBE_API_VERSION,
            http=credentials.authorize(httplib2.Http())
        )

    def search_live_stream(self, channel_id) -> List[str]:
        search_result = self._yt_inst.search().list(
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

    def get_live_chat_id(self, live_stream_id) -> str:
        live_stream_result = self._yt_inst.videos().list(
            part="snippet,contentDetails,liveStreamingDetails",
            id=live_stream_id,
        ).execute()
        write_to_file("python_output2.json", live_stream_result)
        livechat_id = live_stream_result["items"][0]["liveStreamingDetails"]["activeLiveChatId"]
        return livechat_id

    def get_live_chat_data(self, live_chat_id) -> list:
        live_chat_result = self._yt_inst.liveChatMessages().list(
            part="snippet,authorDetails",
            liveChatId=live_chat_id,
            maxResults=2000
        ).execute()
        write_to_file("python_output3.json", live_chat_result)
        return live_chat_result["items"]
