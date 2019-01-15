import asyncio
import json
import os
from oauth2client import file as oauth_file
from oauth2client import client, tools
from getpass import getpass
from aiostream import stream
from src.new_e3 import NewE3
from src.old_e3 import OldE3
from src.downloader import Downloader
from src.gdrive import GDrive


SCOPES = "https://www.googleapis.com/auth/drive"


async def main() -> None:
    new_e3 = NewE3()
    old_e3 = OldE3()

    with open("config.json", "r") as f:
        config = json.loads(f.read())

    username = config.get("studentId", "")
    old_e3_pwd = config.get("oldE3Password", "")
    new_e3_pwd = config.get("newE3Password", "")
    download_path = config.get("downloadPath", "e3")
    gdrive_enable = config.get("gdrive_enable", True)
    download_path = os.path.expanduser(download_path)

    if gdrive_enable:
        store = oauth_file.Storage("token.json")
        creds = store.get()
        if not creds or creds.invalid:
            flow = client.flow_from_clientsecrets("credentials.json", SCOPES)
            creds = tools.run_flow(flow, store)

    while True:
        if username == "":
            username = input("StudentID: ")
        if old_e3_pwd == "":
            old_e3_pwd = getpass("Old E3 Password: ")
        if await old_e3.login(username, old_e3_pwd):
            break
        username, old_e3_pwd = "", ""
        print("ID or Old E3 Password Error")

    while True:
        if new_e3_pwd == "":
            new_e3_pwd = getpass("New E3 Password: ")
        if not new_e3_pwd:
            new_e3_pwd = old_e3_pwd
        if await new_e3.login(username, new_e3_pwd):
            break
        new_e3_pwd = ""
        print("New E3 Password Error")

    downloader = Downloader(download_path)
    async with stream.merge(new_e3.all_files(), old_e3.all_files()).stream() as files:
        async for file in files:
            downloader.add_file(file)
    modified_files = await downloader.done()

    if gdrive_enable:
        gdirve_client = GDrive(download_path)
        await gdirve_client.upload()

    print("")

    if modified_files:
        print("The below files are added or modified")
        modified_files.sort(key=lambda x: x.course_name)
        for modified_file in modified_files:
            print(f"{modified_file.course_name} - {modified_file.name}")
    else:
        print("No files are added or modified")


if __name__ == "__main__":
    asyncio.run(main())
