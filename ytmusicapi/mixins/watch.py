from ytmusicapi.continuations import get_continuations
from ytmusicapi.exceptions import YTMusicServerError, YTMusicUserError
from ytmusicapi.mixins._protocol import MixinProtocol
from ytmusicapi.parsers.playlists import validate_playlist_id
from ytmusicapi.parsers.watch import *
from ytmusicapi.type_alias import JsonList, ParseFuncType, RequestFuncType


class WatchMixin(MixinProtocol):
    async def get_watch_playlist(
        self,
        session,
        proxy = None,
        videoId: str | None = None,
        playlistId: str | None = None,
        limit: int = 25,
        radio: bool = False,
        shuffle: bool = False,
    ) -> dict[str, JsonList | str | None]:
        body = {
            "enablePersistentPlaylistPanel": True,
            "isAudioOnly": True,
            "tunerSettingValue": "AUTOMIX_SETTING_NORMAL",
        }
        if not videoId and not playlistId:
            raise YTMusicUserError("You must provide either a video id, a playlist id, or both")
        if videoId:
            body["videoId"] = videoId
            if not playlistId:
                playlistId = "RDAMVM" + videoId
            if not (radio or shuffle):
                body["watchEndpointMusicSupportedConfigs"] = {
                    "watchEndpointMusicConfig": {
                        "hasPersistentPlaylistPanel": True,
                        "musicVideoType": "MUSIC_VIDEO_TYPE_ATV",
                    }
                }
        is_playlist = False
        if playlistId:
            playlist_id = validate_playlist_id(playlistId)
            is_playlist = playlist_id.startswith("PL") or playlist_id.startswith("OLA")
            body["playlistId"] = playlist_id

        if shuffle and playlistId is not None:
            body["params"] = "wAEB8gECKAE%3D"
        if radio:
            body["params"] = "wAEB"
        endpoint = "next"
        response = await self._send_request_async(session, proxy, endpoint, body)
        watchNextRenderer = nav(
            response,
            [
                "contents",
                "singleColumnMusicWatchNextResultsRenderer",
                "tabbedRenderer",
                "watchNextTabbedResultsRenderer",
            ],
        )

        lyrics_browse_id = get_tab_browse_id(watchNextRenderer, 1)
        related_browse_id = get_tab_browse_id(watchNextRenderer, 2)

        results = nav(
            watchNextRenderer, [*TAB_CONTENT, "musicQueueRenderer", "content", "playlistPanelRenderer"], True
        )
        if not results:
            msg = "No content returned by the server."
            if playlistId:
                msg += f"\nEnsure you have access to {playlistId} - a private playlist may cause this."
            raise YTMusicServerError(msg)

        playlist = next(
            filter(
                bool,
                map(
                    lambda x: nav(x, ["playlistPanelVideoRenderer", *NAVIGATION_PLAYLIST_ID], True),
                    results["contents"],
                ),
            ),
            None,
        )
        tracks = parse_watch_playlist(results["contents"])

        # if "continuations" in results:
        #     print("has continuations")
            # request_func: RequestFuncType = lambda additionalParams: self._send_request(
            #     endpoint, body, additionalParams
            # )
            # parse_func: ParseFuncType = lambda contents: parse_watch_playlist(contents)
            # tracks.extend(
            #     get_continuations(
            #         results,
            #         "playlistPanelContinuation",
            #         limit - len(tracks),
            #         request_func,
            #         parse_func,
            #         "" if is_playlist else "Radio",
            #     )
            # )

        return dict(tracks=tracks, playlistId=playlist, lyrics=lyrics_browse_id, related=related_browse_id)
