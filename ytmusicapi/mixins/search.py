from ytmusicapi.continuations import get_continuations
from ytmusicapi.exceptions import YTMusicUserError
from ytmusicapi.mixins._protocol import MixinProtocol
from ytmusicapi.parsers.search import *
from ytmusicapi.type_alias import JsonList, ParseFuncType, RequestFuncType

class SearchMixin(MixinProtocol):
    async def search(
        self,
        session,
        query: str,
        proxy=None,
        filter: str | None = None,
        scope: str | None = None,
        limit: int = 20,
        ignore_spelling: bool = False,
    ) -> JsonList:
        body = {"query": query}
        endpoint = "search"
        search_results: JsonList = []
        filters = [
            "albums",
            "artists",
            "playlists",
            "community_playlists",
            "featured_playlists",
            "songs",
            "videos",
            "profiles",
            "podcasts",
            "episodes",
        ]
        if filter and filter not in filters:
            raise YTMusicUserError(
                "Invalid filter provided. Please use one of the following filters or leave out the parameter: "
                + ", ".join(filters)
            )

        scopes = ["library", "uploads"]
        if scope and scope not in scopes:
            raise YTMusicUserError(
                "Invalid scope provided. Please use one of the following scopes or leave out the parameter: "
                + ", ".join(scopes)
            )

        if scope == scopes[1] and filter:
            raise YTMusicUserError(
                "No filter can be set when searching uploads. Please unset the filter parameter when scope is set to "
                "uploads. "
            )

        if scope == scopes[0] and filter in filters[3:5]:
            raise YTMusicUserError(
                f"{filter} cannot be set when searching library. "
                f"Please use one of the following filters or leave out the parameter: "
                + ", ".join(filters[0:3] + filters[5:])
            )

        params = get_search_params(filter, scope, ignore_spelling)
        if params:
            body["params"] = params
        response = await self._send_request_async(session, proxy, endpoint, body)
        # no results
        if "contents" not in response:
            return search_results

        if "tabbedSearchResultsRenderer" in response["contents"]:
            tab_index = 0 if not scope or filter else scopes.index(scope) + 1
            results = response["contents"]["tabbedSearchResultsRenderer"]["tabs"][tab_index]["tabRenderer"][
                "content"
            ]
        else:
            results = response["contents"]

        section_list = nav(results, SECTION_LIST)

        # no results
        if len(section_list) == 1 and "itemSectionRenderer" in section_list:
            return search_results

        # set filter for parser
        result_type = None
        if filter and "playlists" in filter:
            filter = "playlists"
        elif scope == scopes[1]:  # uploads
            filter = scopes[1]
            result_type = scopes[1][:-1]

        for res in section_list:
            category = None

            if "musicCardShelfRenderer" in res:
                top_result = parse_top_result(
                    res["musicCardShelfRenderer"], self.parser.get_search_result_types()
                )
                search_results.append(top_result)
                if not (shelf_contents := nav(res, ["musicCardShelfRenderer", "contents"], True)):
                    continue
                # if "more from youtube" is present, remove it - it's not parseable
                if "messageRenderer" in shelf_contents[0]:
                    category = nav(shelf_contents.pop(0), ["messageRenderer", *TEXT_RUN_TEXT])

            elif "musicShelfRenderer" in res:
                shelf_contents = res["musicShelfRenderer"]["contents"]
                category = nav(res, MUSIC_SHELF + TITLE_TEXT, True)

                # if we know the filter it's easy to set the result type
                # unfortunately uploads is modeled as a filter (historical reasons),
                #  so we take care to not set the result type for that scope
                if filter and not scope == scopes[1]:
                    result_type = filter[:-1].lower()

            else:
                continue

            api_search_result_types = self.parser.get_api_result_types()

            search_results.extend(
                parse_search_results(shelf_contents, api_search_result_types, result_type, category)
            )

            if filter:  # if filter is set, there are continuations
                request_func: RequestFuncType = lambda additionalParams: self._send_request(
                    endpoint, body, additionalParams
                )
                parse_func: ParseFuncType = lambda contents: parse_search_results(
                    contents, api_search_result_types, result_type, category
                )

                search_results.extend(
                    get_continuations(
                        res["musicShelfRenderer"],
                        "musicShelfContinuation",
                        limit - len(search_results),
                        request_func,
                        parse_func,
                    )
                )
        return search_results

    def get_search_suggestions(self, query: str, detailed_runs: bool = False) -> list[str] | JsonList:
        body = {"input": query}
        endpoint = "music/get_search_suggestions"

        response = self._send_request(endpoint, body)

        return parse_search_suggestions(response, detailed_runs)

    def remove_search_suggestions(self, suggestions: JsonList, indices: list[int] | None = None) -> bool:
        if not any(run["fromHistory"] for run in suggestions):
            raise YTMusicUserError(
                "No search result from history provided. "
                "Please run get_search_suggestions first to retrieve suggestions. "
                "Ensure that you have searched a similar term before."
            )

        if indices is None:
            indices = list(range(len(suggestions)))

        if any(index >= len(suggestions) for index in indices):
            raise YTMusicUserError("Index out of range. Index must be smaller than the length of suggestions")

        feedback_tokens = [suggestions[index]["feedbackToken"] for index in indices]
        if all(feedback_token is None for feedback_token in feedback_tokens):
            return False

        # filter None tokens
        feedback_tokens = [token for token in feedback_tokens if token is not None]

        body = {"feedbackTokens": feedback_tokens}
        endpoint = "feedback"

        response = self._send_request(endpoint, body)

        return bool(nav(response, ["feedbackResponses", 0, "isProcessed"], none_if_absent=True))
