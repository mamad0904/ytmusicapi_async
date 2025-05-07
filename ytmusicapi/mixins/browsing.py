import re
import warnings
from collections.abc import Callable
from typing import Literal, cast, overload

from ytmusicapi.continuations import (
    get_continuations,
    get_reloadable_continuation_params,
)
from ytmusicapi.helpers import YTM_DOMAIN, sum_total_duration
from ytmusicapi.models.lyrics import LyricLine, Lyrics, TimedLyrics
from ytmusicapi.parsers.albums import parse_album_header_2024
from ytmusicapi.parsers.browsing import (
    parse_album,
    parse_content_list,
    parse_mixed_content,
    parse_playlist,
    parse_video,
)
from ytmusicapi.parsers.library import parse_albums
from ytmusicapi.parsers.playlists import parse_playlist_items
from ytmusicapi.type_alias import JsonDict, JsonList, ParseFuncType, RequestFuncType

from ..exceptions import YTMusicError, YTMusicUserError
from ..navigation import *
from ._protocol import MixinProtocol
from ._utils import get_datestamp


class BrowsingMixin(MixinProtocol):
    def get_home(self, limit: int = 3) -> JsonList:
        """
        Get the home page.
        The home page is structured as titled rows, returning 3 rows of music suggestions at a time.
        Content varies and may contain artist, album, song or playlist suggestions, sometimes mixed within the same row

        :param limit: Number of rows on the home page to return
        :return: List of dictionaries keyed with 'title' text and 'contents' list

        Example list::

            [
                {
                    "title": "Your morning music",
                    "contents": [
                        { //album result
                            "title": "Sentiment",
                            "browseId": "MPREb_QtqXtd2xZMR",
                            "thumbnails": [...]
                        },
                        { //playlist result
                            "title": "r/EDM top submissions 01/28/2022",
                            "playlistId": "PLz7-xrYmULdSLRZGk-6GKUtaBZcgQNwel",
                            "thumbnails": [...],
                            "description": "redditEDM • 161 songs",
                            "count": "161",
                            "author": [
                                {
                                    "name": "redditEDM",
                                    "id": "UCaTrZ9tPiIGHrkCe5bxOGwA"
                                }
                            ]
                        }
                    ]
                },
                {
                    "title": "Your favorites",
                    "contents": [
                        { //artist result
                            "title": "Chill Satellite",
                            "browseId": "UCrPLFBWdOroD57bkqPbZJog",
                            "subscribers": "374",
                            "thumbnails": [...]
                        }
                        { //album result
                            "title": "Dragon",
                            "year": "Two Steps From Hell",
                            "browseId": "MPREb_M9aDqLRbSeg",
                            "thumbnails": [...]
                        }
                    ]
                },
                {
                    "title": "Quick picks",
                    "contents": [
                        { //song quick pick
                            "title": "Gravity",
                            "videoId": "EludZd6lfts",
                            "artists": [{
                                    "name": "yetep",
                                    "id": "UCSW0r7dClqCoCvQeqXiZBlg"
                                }],
                            "thumbnails": [...],
                            "album": {
                                "name": "Gravity",
                                "id": "MPREb_D6bICFcuuRY"
                            }
                        },
                        { //video quick pick
                            "title": "Gryffin & Illenium (feat. Daya) - Feel Good (L3V3LS Remix)",
                            "videoId": "bR5l0hJDnX8",
                            "artists": [
                                {
                                    "name": "L3V3LS",
                                    "id": "UCCVNihbOdkOWw_-ajIYhAbQ"
                                }
                            ],
                            "thumbnails": [...],
                            "views": "10M"
                        }
                    ]
                }
            ]

        """
        endpoint = "browse"
        body = {"browseId": "FEmusic_home"}
        response = self._send_request(endpoint, body)
        results = nav(response, SINGLE_COLUMN_TAB + SECTION_LIST)
        home = []
        home.extend(parse_mixed_content(results))

        section_list = nav(response, [*SINGLE_COLUMN_TAB, "sectionListRenderer"])
        if "continuations" in section_list:
            request_func: RequestFuncType = lambda additionalParams: self._send_request(
                endpoint, body, additionalParams
            )

            parse_func: Callable[[JsonList], JsonList] = lambda contents: parse_mixed_content(contents)

            home.extend(
                get_continuations(
                    section_list, "sectionListContinuation", limit - len(home), request_func, parse_func
                )
            )

        return home

    def get_artist(self, channelId: str) -> JsonDict:
        """
        Get information about an artist and their top releases (songs,
        albums, singles, videos, and related artists). The top lists
        contain pointers for getting the full list of releases.

        Possible content types for get_artist are:

            - songs
            - albums
            - singles
            - shows
            - videos
            - episodes
            - podcasts
            - related

        Each of these content keys in the response contains
        ``results`` and possibly ``browseId`` and ``params``.

        - For songs/videos, pass the browseId to :py:func:`get_playlist`.
        - For albums/singles/shows, pass browseId and params to :py:func:`get_artist_albums`.

        :param channelId: channel id of the artist
        :return: Dictionary with requested information.

        .. warning::

            The returned channelId is not the same as the one passed to the function.
            It should be used only with :py:func:`subscribe_artists`.

        Example::

            {
                "description": "Oasis were ...",
                "views": "3,693,390,359 views",
                "name": "Oasis",
                "channelId": "UCUDVBtnOQi4c7E8jebpjc9Q",
                "shuffleId": "RDAOkjHYJjL1a3xspEyVkhHAsg",
                "radioId": "RDEMkjHYJjL1a3xspEyVkhHAsg",
                "subscribers": "3.86M",
                "subscribed": false,
                "thumbnails": [...],
                "songs": {
                    "browseId": "VLPLMpM3Z0118S42R1npOhcjoakLIv1aqnS1",
                    "results": [
                        {
                            "videoId": "ZrOKjDZOtkA",
                            "title": "Wonderwall (Remastered)",
                            "thumbnails": [...],
                            "artist": "Oasis",
                            "album": "(What's The Story) Morning Glory? (Remastered)"
                        }
                    ]
                },
                "albums": {
                    "results": [
                        {
                            "title": "Familiar To Millions",
                            "thumbnails": [...],
                            "year": "2018",
                            "browseId": "MPREb_AYetWMZunqA"
                        }
                    ],
                    "browseId": "UCmMUZbaYdNH0bEd1PAlAqsA",
                    "params": "6gPTAUNwc0JDbndLYlFBQV..."
                },
                "singles": {
                    "results": [
                        {
                            "title": "Stand By Me (Mustique Demo)",
                            "thumbnails": [...],
                            "year": "2016",
                            "browseId": "MPREb_7MPKLhibN5G"
                        }
                    ],
                    "browseId": "UCmMUZbaYdNH0bEd1PAlAqsA",
                    "params": "6gPTAUNwc0JDbndLYlFBQV..."
                },
                "videos": {
                    "results": [
                        {
                            "title": "Wonderwall",
                            "thumbnails": [...],
                            "views": "358M",
                            "videoId": "bx1Bh8ZvH84",
                            "playlistId": "PLMpM3Z0118S5xuNckw1HUcj1D021AnMEB"
                        }
                    ],
                    "browseId": "VLPLMpM3Z0118S5xuNckw1HUcj1D021AnMEB"
                },
                "related": {
                    "results": [
                        {
                            "browseId": "UCt2KxZpY5D__kapeQ8cauQw",
                            "subscribers": "450K",
                            "title": "The Verve"
                        },
                        {
                            "browseId": "UCwK2Grm574W1u-sBzLikldQ",
                            "subscribers": "341K",
                            "title": "Liam Gallagher"
                        },
                        ...
                    ]
                }
            }
        """
        if channelId.startswith("MPLA"):
            channelId = channelId[4:]
        body = {"browseId": channelId}
        endpoint = "browse"
        response = self._send_request(endpoint, body)
        results = nav(response, SINGLE_COLUMN_TAB + SECTION_LIST)

        artist: JsonDict = {"description": None, "views": None}
        header = response["header"]["musicImmersiveHeaderRenderer"]
        artist["name"] = nav(header, TITLE_TEXT)
        descriptionShelf = find_object_by_key(results, DESCRIPTION_SHELF[0], is_key=True)
        if descriptionShelf:
            artist["description"] = nav(descriptionShelf, DESCRIPTION)
            artist["views"] = (
                None
                if "subheader" not in descriptionShelf
                else descriptionShelf["subheader"]["runs"][0]["text"]
            )
        subscription_button = header["subscriptionButton"]["subscribeButtonRenderer"]
        artist["channelId"] = subscription_button["channelId"]
        artist["shuffleId"] = nav(header, ["playButton", "buttonRenderer", *NAVIGATION_PLAYLIST_ID], True)
        artist["radioId"] = nav(header, ["startRadioButton", "buttonRenderer", *NAVIGATION_PLAYLIST_ID], True)
        artist["subscribers"] = nav(subscription_button, ["subscriberCountText", "runs", 0, "text"], True)
        artist["subscribed"] = subscription_button["subscribed"]
        artist["thumbnails"] = nav(header, THUMBNAILS, True)
        artist["songs"] = {"browseId": None}
        if "musicShelfRenderer" in results[0]:  # API sometimes does not return songs
            musicShelf = nav(results[0], MUSIC_SHELF)
            if "navigationEndpoint" in nav(musicShelf, TITLE):
                artist["songs"]["browseId"] = nav(musicShelf, TITLE + NAVIGATION_BROWSE_ID)
            artist["songs"]["results"] = parse_playlist_items(musicShelf["contents"])

        artist.update(self.parser.parse_channel_contents(results))
        return artist

    ArtistOrderType = Literal["Recency", "Popularity", "Alphabetical order"]

    def get_artist_albums(
        self, channelId: str, params: str, limit: int | None = 100, order: ArtistOrderType | None = None
    ) -> JsonList:
        """
        Get the full list of an artist's albums, singles or shows

        :param channelId: browseId of the artist as returned by :py:func:`get_artist`
        :param params: params obtained by :py:func:`get_artist`
        :param limit: Number of albums to return. ``None`` retrieves them all. Default: 100
        :param order: Order of albums to return. Allowed values: ``Recency``, ``Popularity``, `Alphabetical order`. Default: Default order.
        :return: List of albums in the format of :py:func:`get_library_albums`,
          except artists key is missing.

        """
        body = {"browseId": channelId, "params": params}
        endpoint = "browse"
        response = self._send_request(endpoint, body)

        request_func: RequestFuncType = lambda additionalParams: self._send_request(
            endpoint, body, additionalParams
        )
        parse_func: ParseFuncType = lambda contents: parse_albums(contents)

        if order:
            # pick the correct continuation from response depending on the order chosen
            sort_options = nav(
                response,
                SINGLE_COLUMN_TAB
                + SECTION
                + HEADER_SIDE
                + [
                    "endItems",
                    0,
                    "musicSortFilterButtonRenderer",
                    "menu",
                    "musicMultiSelectMenuRenderer",
                    "options",
                ],
            )
            continuation = next(
                (
                    nav(
                        option,
                        [
                            *MULTI_SELECT,
                            "selectedCommand",
                            "commandExecutorCommand",
                            "commands",
                            -1,
                            "browseSectionListReloadEndpoint",
                        ],
                    )
                    for option in sort_options
                    if nav(option, MULTI_SELECT + TITLE_TEXT).lower() == order.lower()
                ),
                None,
            )
            # if a valid order was provided, request continuation and replace original response
            if continuation:
                additionalParams = get_reloadable_continuation_params(
                    {"continuations": [continuation["continuation"]]}
                )
                response = request_func(additionalParams)
                results = nav(response, SECTION_LIST_CONTINUATION + CONTENT)
            else:
                raise ValueError(f"Invalid order parameter {order}")

        else:
            # just use the results from the first request
            results = nav(response, SINGLE_COLUMN_TAB + SECTION_LIST_ITEM)

        contents = nav(results, GRID_ITEMS, True) or nav(results, CAROUSEL_CONTENTS)
        albums = parse_albums(contents)

        results = nav(results, GRID, True)
        if "continuations" in results:
            remaining_limit = None if limit is None else (limit - len(albums))
            albums.extend(
                get_continuations(results, "gridContinuation", remaining_limit, request_func, parse_func)
            )

        return albums

    def get_user(self, channelId: str) -> JsonDict:
        """
        Retrieve a user's page. A user may own videos or playlists.

        Use :py:func:`get_user_playlists` to retrieve all playlists::

            result = get_user(channelId)
            get_user_playlists(channelId, result["playlists"]["params"])

        Similarly, use :py:func:`get_user_videos` to retrieve all videos::

            get_user_videos(channelId, result["videos"]["params"])

        :param channelId: channelId of the user
        :return: Dictionary with information about a user.

        Example::

            {
              "name": "4Tune - No Copyright Music",
              "videos": {
                "browseId": "UC44hbeRoCZVVMVg5z0FfIww",
                "results": [
                  {
                    "title": "Epic Music Soundtracks 2019",
                    "videoId": "bJonJjgS2mM",
                    "playlistId": "RDAMVMbJonJjgS2mM",
                    "thumbnails": [
                      {
                        "url": "https://i.ytimg.com/vi/bJon...",
                        "width": 800,
                        "height": 450
                      }
                    ],
                    "views": "19K"
                  }
                ]
              },
              "playlists": {
                "browseId": "UC44hbeRoCZVVMVg5z0FfIww",
                "results": [
                  {
                    "title": "♚ Machinimasound | Playlist",
                    "playlistId": "PLRm766YvPiO9ZqkBuEzSTt6Bk4eWIr3gB",
                    "thumbnails": [
                      {
                        "url": "https://i.ytimg.com/vi/...",
                        "width": 400,
                        "height": 225
                      }
                    ]
                  }
                ],
                "params": "6gO3AUNvWU..."
              }
            }
        """
        endpoint = "browse"
        body = {"browseId": channelId}
        response = self._send_request(endpoint, body)
        user = {"name": nav(response, [*HEADER_MUSIC_VISUAL, *TITLE_TEXT])}
        results = nav(response, SINGLE_COLUMN_TAB + SECTION_LIST)
        user.update(self.parser.parse_channel_contents(results))
        return user

    def get_user_playlists(self, channelId: str, params: str) -> JsonList:
        """
        Retrieve a list of playlists for a given user.
        Call this function again with the returned ``params`` to get the full list.

        :param channelId: channelId of the user.
        :param params: params obtained by :py:func:`get_user`
        :return: List of user playlists in the format of :py:func:`get_library_playlists`

        """
        endpoint = "browse"
        body = {"browseId": channelId, "params": params}
        response = self._send_request(endpoint, body)
        results = nav(response, SINGLE_COLUMN_TAB + SECTION_LIST_ITEM + GRID_ITEMS, True)
        if not results:
            return []

        user_playlists = parse_content_list(results, parse_playlist)

        return user_playlists

    def get_user_videos(self, channelId: str, params: str) -> JsonList:
        """
        Retrieve a list of videos for a given user.
        Call this function again with the returned ``params`` to get the full list.

        :param channelId: channelId of the user.
        :param params: params obtained by :py:func:`get_user`
        :return: List of user videos

        """
        endpoint = "browse"
        body = {"browseId": channelId, "params": params}
        response = self._send_request(endpoint, body)
        results = nav(response, SINGLE_COLUMN_TAB + SECTION_LIST_ITEM + GRID_ITEMS, True)
        if not results:
            return []

        user_videos = parse_content_list(results, parse_video)

        return user_videos

    def get_album_browse_id(self, audioPlaylistId: str) -> str | None:
        """
        Get an album's browseId based on its audioPlaylistId

        :param audioPlaylistId: id of the audio playlist  (starting with `OLAK5uy_`)
        :return: browseId (starting with ``MPREb_``)
        """
        params = {"list": audioPlaylistId}
        response = self._send_get_request(YTM_DOMAIN + "/playlist", params)

        with warnings.catch_warnings():
            # merge this with statement with catch_warnings on Python>=3.11
            warnings.simplefilter(action="ignore", category=DeprecationWarning)
            decoded = response.text.encode("utf8").decode("unicode_escape")

        matches = re.search(r"\"MPRE.+?\"", decoded)
        browse_id = None
        if matches:
            browse_id = matches.group().strip('"')
        return browse_id

    def get_album(self, browseId: str) -> JsonDict:
        """
        Get information and tracks of an album

        :param browseId: browseId of the album, for example
            returned by :py:func:`search`
        :return: Dictionary with album and track metadata.

        The result is in the following format::

            {
              "title": "Revival",
              "type": "Album",
              "thumbnails": [],
              "description": "Revival is the...",
              "artists": [
                {
                  "name": "Eminem",
                  "id": "UCedvOgsKFzcK3hA5taf3KoQ"
                }
              ],
              "year": "2017",
              "trackCount": 19,
              "duration": "1 hour, 17 minutes",
              "audioPlaylistId": "OLAK5uy_nMr9h2VlS-2PULNz3M3XVXQj_P3C2bqaY",
              "tracks": [
                {
                  "videoId": "iKLU7z_xdYQ",
                  "title": "Walk On Water (feat. Beyoncé)",
                  "artists": [
                    {
                      "name": "Eminem",
                      "id": "UCedvOgsKFzcK3hA5taf3KoQ"
                    }
                  ],
                  "album": "Revival",
                  "likeStatus": "INDIFFERENT",
                  "thumbnails": null,
                  "isAvailable": true,
                  "isExplicit": true,
                  "duration": "5:03",
                  "duration_seconds": 303,
                  "trackNumber": 0,
                  "feedbackTokens": {
                    "add": "AB9zfpK...",
                    "remove": "AB9zfpK..."
                  }
                }
              ],
              "other_versions": [
                {
                  "title": "Revival",
                  "year": "Eminem",
                  "browseId": "MPREb_fefKFOTEZSp",
                  "thumbnails": [...],
                  "isExplicit": false
                },
              ],
              "duration_seconds": 4657
            }
        """
        if not browseId or not browseId.startswith("MPRE"):
            raise YTMusicUserError("Invalid album browseId provided, must start with MPRE.")

        body = {"browseId": browseId}
        endpoint = "browse"
        response = self._send_request(endpoint, body)
        album: JsonDict = parse_album_header_2024(response)

        results = nav(response, [*TWO_COLUMN_RENDERER, "secondaryContents", *SECTION_LIST_ITEM, *MUSIC_SHELF])
        album["tracks"] = parse_playlist_items(results["contents"], is_album=True)

        other_versions = nav(
            response, [*TWO_COLUMN_RENDERER, "secondaryContents", *SECTION_LIST, 1, *CAROUSEL], True
        )
        if other_versions is not None:
            album["other_versions"] = parse_content_list(other_versions["contents"], parse_album)
        album["duration_seconds"] = sum_total_duration(album)
        for i, track in enumerate(album["tracks"]):
            album["tracks"][i]["album"] = album["title"]
            album["tracks"][i]["artists"] = album["tracks"][i]["artists"] or album["artists"]

        return album


    async def get_song(self, session, videoId: str, signatureTimestamp: int | None = None, proxy = None) -> JsonDict:
        endpoint = "player"
        if not signatureTimestamp:
            signatureTimestamp = get_datestamp() - 1

        params = {
            "playbackContext": {"contentPlaybackContext": {"signatureTimestamp": signatureTimestamp}},
            "video_id": videoId,
        }
        response = await self._send_request_async(session, proxy, endpoint, params)
        keys = ["videoDetails", "playabilityStatus", "streamingData", "microformat", "playbackTracking"]
        for k in list(response.keys()):
            if k not in keys:
                del response[k]
        return response

    def get_song_related(self, browseId: str) -> JsonList:
        if not browseId:
            raise YTMusicUserError("Invalid browseId provided.")

        response = self._send_request("browse", {"browseId": browseId})
        sections = nav(response, ["contents", *SECTION_LIST])
        return parse_mixed_content(sections)

    @overload
    def get_lyrics(self, browseId: str, timestamps: Literal[False] = False) -> Lyrics | None:
        """overload for mypy only"""

    @overload
    def get_lyrics(self, browseId: str, timestamps: Literal[True] = True) -> Lyrics | TimedLyrics | None:
        """overload for mypy only"""

    def get_lyrics(self, browseId: str, timestamps: bool | None = False) -> Lyrics | TimedLyrics | None:
        """
        Returns lyrics of a song or video. When `timestamps` is set, lyrics are returned with
        timestamps, if available.

        :param browseId: Lyrics browseId obtained from :py:func:`get_watch_playlist` (startswith ``MPLYt...``).
        :param timestamps: Optional. Whether to return bare lyrics or lyrics with timestamps, if available. (Default: `False`)
        :return: Dictionary with song lyrics or ``None``, if no lyrics are found.
            The ``hasTimestamps``-key determines the format of the data.


            Example when `timestamps=False`, or no timestamps are available::

                {
                    "lyrics": "Today is gonna be the day\\nThat they're gonna throw it back to you\\n",
                    "source": "Source: LyricFind",
                    "hasTimestamps": False
                }

            Example when `timestamps` is set to `True` and timestamps are available::

                {
                    "lyrics": [
                        LyricLine(
                            text="I was a liar",
                            start_time=9200,
                            end_time=10630,
                            id=1
                        ),
                        LyricLine(
                            text="I gave in to the fire",
                            start_time=10680,
                            end_time=12540,
                            id=2
                        ),
                    ],
                    "source": "Source: LyricFind",
                    "hasTimestamps": True
                }

        """
        if not browseId:
            raise YTMusicUserError("Invalid browseId provided. This song might not have lyrics.")

        if timestamps:
            # changes and restores the client to get lyrics with timestamps (mobile only)
            with self.as_mobile():
                response = self._send_request("browse", {"browseId": browseId})
        else:
            response = self._send_request("browse", {"browseId": browseId})

        # unpack the response
        lyrics: Lyrics | TimedLyrics
        if timestamps and (data := nav(response, TIMESTAMPED_LYRICS, True)) is not None:
            # we got lyrics with timestamps
            assert isinstance(data, dict)

            if "timedLyricsData" not in data:  # pragma: no cover
                return None

            lyrics = TimedLyrics(
                lyrics=list(map(LyricLine.from_raw, data["timedLyricsData"])),
                source=data.get("sourceMessage"),
                hasTimestamps=True,
            )
        else:
            lyrics_str = nav(
                response, ["contents", *SECTION_LIST_ITEM, *DESCRIPTION_SHELF, *DESCRIPTION], True
            )

            if lyrics_str is None:  # pragma: no cover
                return None

            lyrics = Lyrics(
                lyrics=lyrics_str,
                source=nav(response, ["contents", *SECTION_LIST_ITEM, *DESCRIPTION_SHELF, *RUN_TEXT], True),
                hasTimestamps=False,
            )

        return cast(Lyrics | TimedLyrics, lyrics)

    def get_basejs_url(self) -> str:
        """
        Extract the URL for the `base.js` script from YouTube Music.

        :return: URL to `base.js`
        """
        response = self._send_get_request(url=YTM_DOMAIN)
        match = re.search(r'jsUrl"\s*:\s*"([^"]+)"', response.text)
        if match is None:
            raise YTMusicError("Could not identify the URL for base.js player.")

        return YTM_DOMAIN + match.group(1)

    def get_signatureTimestamp(self, url: str | None = None) -> int:
        """
        Fetch the `base.js` script from YouTube Music and parse out the
        ``signatureTimestamp`` for use with :py:func:`get_song`.

        :param url: Optional. Provide the URL of the `base.js` script. If this
            isn't specified a call will be made to :py:func:`get_basejs_url`.
        :return: ``signatureTimestamp`` string
        """
        if url is None:
            url = self.get_basejs_url()
        response = self._send_get_request(url=url)
        match = re.search(r"signatureTimestamp[:=](\d+)", response.text)
        if match is None:
            raise YTMusicError("Unable to identify the signatureTimestamp.")

        return int(match.group(1))

    def get_tasteprofile(self) -> JsonDict:
        """
        Fetches suggested artists from taste profile (music.youtube.com/tasteprofile). Must be authenticated.
        Tasteprofile allows users to pick artists to update their recommendations.
        Only returns a list of suggested artists, not the actual list of selected entries

        :return: Dictionary with artist and their selection & impression value

        Example::

            {
                "Drake": {
                    "selectionValue": "tastebuilder_selection=/m/05mt_q"
                    "impressionValue": "tastebuilder_impression=/m/05mt_q"
                }
            }

        """
        self._check_auth()
        response = self._send_request("browse", {"browseId": "FEmusic_tastebuilder"})
        profiles = nav(response, TASTE_PROFILE_ITEMS)

        taste_profiles = {}
        for itemList in profiles:
            for item in itemList["tastebuilderItemListRenderer"]["contents"]:
                artist = nav(item["tastebuilderItemRenderer"], TASTE_PROFILE_ARTIST)[0]["text"]
                taste_profiles[artist] = {
                    "selectionValue": item["tastebuilderItemRenderer"]["selectionFormValue"],
                    "impressionValue": item["tastebuilderItemRenderer"]["impressionFormValue"],
                }
        return taste_profiles

    def set_tasteprofile(self, artists: list[str], taste_profile: JsonDict | None = None) -> None:
        """
        Favorites artists to see more recommendations from the artist.
        Use :py:func:`get_tasteprofile` to see which artists are available to be recommended

        :param artists: A List with names of artists, must be contained in the tasteprofile
        :param taste_profile: tasteprofile result from :py:func:`get_tasteprofile`.
            Pass this if you call :py:func:`get_tasteprofile` anyway to save an extra request.
        :return: None if successful
        """

        if taste_profile is None:
            taste_profile = self.get_tasteprofile()
        formData = {
            "impressionValues": [taste_profile[profile]["impressionValue"] for profile in taste_profile],
            "selectedValues": [],
        }

        for artist in artists:
            if artist not in taste_profile:
                raise YTMusicUserError(f"The artist {artist} was not present in taste!")
            formData["selectedValues"].append(taste_profile[artist]["selectionValue"])

        body = {"browseId": "FEmusic_home", "formData": formData}
        self._send_request("browse", body)
