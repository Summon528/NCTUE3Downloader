from typing import Union, Any
from yarl import URL
from bs4 import BeautifulSoup
from aiohttp import ClientSession

StrOrURL = Union[str, URL]


class ASPSession:
    def __init__(self):
        self.__view_state = ""
        self.__client_session = ClientSession()

    async def get(
        self, url: StrOrURL, *, allow_redirects: bool = False, **kwargs
    ) -> BeautifulSoup:
        resp = await self.__client_session.get(
            url, allow_redirects=allow_redirects, **kwargs
        )
        soup = BeautifulSoup(await resp.text(), "html.parser")
        el = soup.find(id="__VIEWSTATE")
        if el:
            self.__view_state = el["value"]
        return soup

    async def post(
        self,
        url: StrOrURL,
        *,
        data: Any = None,
        allow_redirects: bool = False,
        **kwargs
    ):
        if data is None:
            data = {}
        if self.__view_state:
            data["__VIEWSTATE"] = self.__view_state
        return await self.__client_session.post(
            url, data=data, allow_redirects=allow_redirects, **kwargs
        )

    async def close(self) -> None:
        await self.__client_session.close()
