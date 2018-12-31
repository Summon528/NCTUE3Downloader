import asyncio
import json
import os
from getpass import getpass
from aiostream import stream
from new_e3 import NewE3
from old_e3 import OldE3
from downloader import Downloader


async def main() -> None:
    new_e3 = NewE3()
    old_e3 = OldE3()

    with open("config.json", "r") as f:
        config = json.loads(f.read())

    username = config.get("studentId", None)
    old_e3_pwd = config.get("oldE3Password", None)
    new_e3_pwd = config.get("newE3Password", None)
    download_path = config.get("downloadPath", "e3")

    while True:
        if username is None:
            username = input('StudentID: ')
        if old_e3_pwd is None:
            old_e3_pwd = getpass('Old E3 Password: ')
        if await old_e3.login(username, old_e3_pwd):
            break
        username, old_e3_pwd = None, None
        print("ID or Old E3 Password Error")

    while True:
        if new_e3_pwd is None:
            new_e3_pwd = getpass('New E3 Password: ')
        if not new_e3_pwd:
            new_e3_pwd = old_e3_pwd
        if await new_e3.login(username, new_e3_pwd):
            break
        new_e3_pwd = None
        print("New E3 Password Error")

    downloader = Downloader(download_path)
    async with stream.merge(new_e3.all_files(),
                            old_e3.all_files()).stream() as files:
        async for file in files:
            downloader.add_file(file)
    await downloader.done()


if __name__ == "__main__":
    asyncio.run(main())
