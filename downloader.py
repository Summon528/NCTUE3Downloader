import asyncio
import math
import string
import aiohttp
import shelve
import os
from tqdm import tqdm
from models import E3File
from typing import List, Coroutine, Tuple
import sys


class Downloader():
    def __init__(self) -> None:
        self.queue: 'asyncio.Queue[E3File]' = asyncio.Queue()
        self.session = aiohttp.ClientSession()
        self.eng_char = set(string.printable)
        self.tasks = [asyncio.create_task(self.worker(i)) for i in range(4)]
        self.db = shelve.open('db.shelve')
        self.progressbar = tqdm(desc='File Found', position=0)

    async def worker(self, idx) -> None:
        timeout = aiohttp.ClientTimeout(total=10)
        while True:
            file: E3File = await self.queue.get()
            short_file_name = ''.join(filter(lambda x: x in self.eng_char,
                                             file.name))[:25]
            if file.timemodified is None and self.db.get(file.hash_val, -1) != -1 \
                    or file.timemodified == self.db.get(file.hash_val, -1):
                self.queue.task_done()
                continue
            progressbar = tqdm(
                desc=short_file_name,
                unit='B',
                total=float('inf'),
                unit_scale=True,
                unit_divisor=1024,
                position=idx+1
            )
            try:
                resp = await self.session.get(file.url, timeout=timeout)
            except asyncio.TimeoutError:
                self.queue.task_done()
                continue
            file_dir = os.path.join('e3', file.course_name)
            if not os.path.exists(file_dir):
                os.makedirs(file_dir)
            total_size = int(resp.headers.get('content-length', 0))
            progressbar.total = total_size
            self.db[file.hash_val] = file.timemodified
            with open(os.path.join(file_dir, file.name), mode='wb') as f, progressbar:
                while True:
                    chunk = await resp.content.read(1024)
                    if not chunk:
                        break
                    progressbar.update(len(chunk))
                    f.write(chunk)
            self.queue.task_done()

    def add_file(self, file: E3File):
        self.progressbar.update(1)
        self.queue.put_nowait(file)

    async def done(self):
        self.progressbar.close()
        await self.queue.join()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.session.close()
