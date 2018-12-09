import asyncio
from getpass import getpass
from multiprocessing import Pool
from aiostream import stream
from new_e3 import NewE3
from old_e3 import OldE3
from downloader import Downloader


async def main():
    username = input('StudentID: ')
    old_e3_pwd = getpass('Old E3 Password: ')
    new_e3_pwd = getpass('New E3 Password: ')
    new_e3 = NewE3()
    old_e3 = OldE3()
    downloader = Downloader()
    async with stream.merge(new_e3.all_files(username, new_e3_pwd),
                            old_e3.all_files(username, old_e3_pwd
                                             )).stream() as files:
        async for file in files:
            if "網路程式設計概論" not in file.course_name:
                downloader.add_file(file)
    await downloader.done()

if __name__ == "__main__":
    asyncio.run(main())
