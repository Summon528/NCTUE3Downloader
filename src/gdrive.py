import httplib2
import os
import shelve
import asyncio
import json
import googleapiclient.discovery
from googleapiclient.http import MediaFileUpload
from oauth2client import file as oauth_file
from .gdrive_executor import GDriveExecutor


class GDrive:
    def __init__(self, download_path: str) -> None:
        self.download_path = download_path
        self.gdrive_executor = GDriveExecutor()

    async def upload(self) -> None:
        store = oauth_file.Storage("token.json")
        creds = store.get()
        service = googleapiclient.discovery.build(
            "drive", "v3", http=creds.authorize(httplib2.Http())
        )

        if not os.path.isfile("root_folder_id.txt"):
            file_metadata = {
                "name": "NCTU_E3",
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = service.files().create(body=file_metadata, fields="id").execute()
            root_folder_id = folder.get("id")
            with open("root_folder_id.txt", "w") as f:
                f.write(root_folder_id)
        else:
            with open("root_folder_id.txt", "r") as f:
                root_folder_id = f.read()

        results = (
            service.files()
            .list(
                pageSize=1000,
                q=f"'{root_folder_id}' in parents and trashed=false",
                fields="files(name, id, trashed)",
            )
            .execute()
        )
        folder_id_map = dict([(i["name"], i["id"]) for i in results.get("files", [])])
        md5_db = shelve.open(os.path.join(self.download_path, "md5_db.shelve"))

        for course in os.listdir(self.download_path):
            course_path = os.path.join(self.download_path, course)
            if not os.path.isdir(course_path):
                continue
            if course not in folder_id_map:
                file_metadata = {
                    "name": course,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [root_folder_id],
                }
                folder = (
                    service.files().create(body=file_metadata, fields="id").execute()
                )
                folder_id_map[course] = folder.get("id")

            results = (
                service.files()
                .list(
                    pageSize=1000,
                    q=f"'{folder_id_map[course]}' in parents and trashed=false",
                    fields="files(name, id, md5Checksum)",
                )
                .execute()
            )

            gdrive_map = dict(
                [
                    (i["name"], (i["id"], i["md5Checksum"]))
                    for i in results.get("files", [])
                ]
            )

            for course_file in os.listdir(course_path):
                if course_file not in gdrive_map:
                    file_metadata = {
                        "name": course_file,
                        "parents": [folder_id_map[course]],
                    }
                    media = MediaFileUpload(os.path.join(course_path, course_file))
                    self.gdrive_executor.add_job(
                        course_file,
                        service.files().create(
                            body=file_metadata, media_body=media, fields="id"
                        ),
                    )
                else:
                    file_id, file_md5 = gdrive_map[course_file]
                    if md5_db.get(repr((course, course_file)), None) == file_md5:
                        self.gdrive_executor.ignore()
                        continue
                    media = MediaFileUpload(os.path.join(course_path, course_file))
                    self.gdrive_executor.add_job(
                        course_file,
                        service.files().update(
                            fileId=file_id, media_body=media, fields="id"
                        ),
                    )
        await self.gdrive_executor.done()


async def main():
    with open("config.json", "r") as f:
        config = json.loads(f.read())
        download_path = config["downloadPath"]
    download_path = os.path.expanduser(download_path)
    gdrive = GDrive(download_path)
    await gdrive.upload()


if __name__ == "__main__":
    asyncio.run(main())
