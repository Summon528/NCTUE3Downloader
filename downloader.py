import asyncio
import string
import shelve
import os
import traceback
import hashlib
import platform
import aiohttp
from tqdm import tqdm
from models import E3File


class Downloader:
    eng_char = set(string.printable)

    def __init__(self, download_path) -> None:
        self.queue: "asyncio.Queue[E3File]" = asyncio.Queue()
        self.session = aiohttp.ClientSession()
        self.tasks = [asyncio.create_task(self.worker(i)) for i in range(4)]
        if not os.path.exists(download_path):
            os.makedirs(download_path)
        self.db = shelve.open(os.path.join(download_path, "db.shelve"))
        self.md5_db = shelve.open(os.path.join(download_path, "md5_db.shelve"))
        self.total = 0
        self.processed = 0
        self.progressbar = tqdm(position=0, bar_format="{desc}", total=1)
        self.progressbar.set_description_str("Initializing...")
        self.download_path = download_path

    def update_bar(self) -> None:
        self.progressbar.set_description_str(
            f"Download - File processed: {self.processed}/{self.total}"
        )

    async def worker(self, idx) -> None:
        while True:
            file: E3File = await self.queue.get()
            try:
                short_file_name = "".join(
                    filter(lambda x: x in self.eng_char, file.name)
                )[:25]
                progressbar = tqdm(
                    desc=short_file_name,
                    unit="B",
                    total=float("inf"),
                    unit_scale=True,
                    unit_divisor=1024,
                    position=idx + 1,
                    ascii=platform.system() == "Windows",
                )
                try:
                    resp = await self.session.get(file.url)
                except aiohttp.client_exceptions.ServerDisconnectedError:
                    self.queue.put_nowait(file)
                    self.queue.task_done()
                    progressbar.close()
                    continue
                file_dir = os.path.join(self.download_path, file.course_name)
                if not os.path.exists(file_dir):
                    os.makedirs(file_dir)
                total_size = int(resp.headers.get("content-length", 0))
                progressbar.total = total_size
                hash_md5 = hashlib.md5()
                file_name_split = file.name.split(".")
                file_name = ".".join(file_name_split[:1]) + "." + file.hash_val[:4]
                if len(file_name_split) >= 2:
                    file_name += "." + file_name_split[-1]
                file_path = os.path.join(file_dir, file_name)
                with open(file_path, mode="wb") as f:
                    with progressbar:
                        while True:
                            chunk = await resp.content.read(1024)
                            if not chunk:
                                break
                            progressbar.update(len(chunk))
                            f.write(chunk)
                            hash_md5.update(chunk)
                self.processed += 1
                self.update_bar()
                self.md5_db[repr((file.course_name, file_name))] = hash_md5.hexdigest()
                self.db[file.hash_val] = file.timemodified
                self.queue.task_done()
            except Exception:
                tqdm.write("-" * 5)
                tqdm.write(f"Exception occurred " f"when downloading '{file.name}'")
                tb = traceback.format_exc()
                tqdm.write(tb)
                self.processed += 1
                self.update_bar()
                self.queue.task_done()
                continue

    def add_file(self, file: E3File) -> None:
        self.total += 1
        if (
            file.timemodified is None
            and self.db.get(file.hash_val, -1) != -1
            or file.timemodified == self.db.get(file.hash_val, -1)
        ):
            self.processed += 1
        else:
            self.queue.put_nowait(file)
        self.update_bar()

    async def done(self) -> None:
        await self.queue.join()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.session.close()
        self.db.close()
        self.md5_db.close()
        self.progressbar.close()
