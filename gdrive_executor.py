import asyncio
import concurrent
import httplib2
from oauth2client import file as oauth_file
from tqdm import tqdm
import googleapiclient.discovery


class GDriveExecutor:
    def __init__(self) -> None:
        self.queue = asyncio.Queue()
        self.tasks = [asyncio.create_task(self.worker(i)) for i in range(4)]
        self.total = 0
        self.processed = 0
        self.progressbar = tqdm(position=0, bar_format="{desc}", total=1)
        self.progressbar.set_description_str("Initializing GDrive...")

    def update_bar(self) -> None:
        self.progressbar.set_description_str(
            f"Upload - File processed: {self.processed}/{self.total}"
        )

    async def worker(self, idx):
        loop = asyncio.get_running_loop()
        http = httplib2.Http()
        store = oauth_file.Storage("token.json")
        creds = store.get()
        service = googleapiclient.discovery.build(
            "drive", "v3", http=creds.authorize(http)
        )
        progressbar = tqdm(position=idx + 1, bar_format="{desc}", total=1)
        while True:
            name, job = await self.queue.get()
            progressbar.set_description_str(name)
            await loop.run_in_executor(None, lambda: job.execute(http=http))
            self.processed += 1
            self.update_bar()
            self.queue.task_done()

    def add_job(self, name, job) -> None:
        self.total += 1
        self.queue.put_nowait((name, job))
        self.update_bar()

    def ignore(self):
        self.total += 1
        self.processed += 1
        self.update_bar()

    async def done(self) -> None:
        await self.queue.join()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.progressbar.close()
