import asyncio
import json
import re
import time
from getpass import getpass
from typing import Dict, Iterable, AsyncIterable
from aiohttp import ClientSession
from models import E3File, Folder, Course, FolderType
from utils import sha1_hash2


class NewE3:

    def __init__(self):
        self._api_url = "https://e3new.nctu.edu.tw/webservice/rest/server.php?moodlewsrestformat=json"
        self._session = None
        self.token = None
        self.userid = None

    async def _get_token(self,
                         username: str,
                         password: str) -> str:
        resp = await self._session.post('https://e3new.nctu.edu.tw/login/token.php', data={
            'username': username,
            'password': password,
            'service': 'moodle_mobile_app'
        })
        return json.loads(await resp.text())['token']

    async def _get_userid(self,
                          username: str,
                          token: str) -> str:
        resp = await self._session.post(self._api_url, data={
            'wsfunction': 'core_user_get_users_by_field',
            'values[0]': username,
            'field': 'username',
            'wstoken': token
        })
        return json.loads(await resp.text())[0]['id']

    @staticmethod
    def _scrub_course_name(course_name: str) -> str:
        try:
            return course_name.split('.')[2].split()[0]
        except IndexError:
            return course_name

    async def __get_course_list(self,
                                userid: str,
                                token: str) -> Iterable[Course]:
        resp = await self._session.post(self._api_url, data={
            'wsfunction': 'core_enrol_get_users_courses',
            'userid': userid,
            'wstoken': token
        })
        resp_json = json.loads(await resp.text())
        return (
            Course(
                str(course['id']),
                self._scrub_course_name(course['fullname'])
            ) for course in resp_json if course['enddate'] > time.time())

    async def _get_folders(self,
                           token: str,
                           courses: Iterable[Course]) -> Iterable[Folder]:
        payload = {
            'wsfunction': 'mod_folder_get_folders_by_courses',
            'wstoken': token,
        }
        for idx, (courseid, _) in enumerate(courses):
            payload[f'courseids[{idx}]'] = courseid
        resp = await self._session.post(self._api_url, data=payload)
        folders = json.loads(await resp.text())['folders']
        return (
            Folder(
                FolderType.REFERENCE
                if folder['name'].startswith("[Reference]") or folder['name'].startswith("[參考資料]")
                else FolderType.HANDOUT,
                folder['name'],
                str(folder['coursemodule']),
                str(folder['course']),
            ) for folder in folders)

    async def _get_materials(self,
                             token: str,
                             course_name: str,
                             folder: Folder) -> Iterable[E3File]:
        resp = await self._session.post(self._api_url, data={
            'courseid': folder.course_id,
            'options[0][value]': folder.folder_id,
            'options[0][name]': 'cmid',
            'wsfunction': 'core_course_get_contents',
            'wstoken': token
        })
        resp_json = json.loads(await resp.text())
        files = [x['modules'][0]
                 for x in resp_json if len(x['modules'])][0]['contents']
        return (
            E3File(
                file['filename'],
                course_name,
                sha1_hash2(folder.folder_id, file['filename']),
                file['fileurl'] + "&token=" + token,
                file['timemodified']
            ) for file in files if not re.match(r'.*\.[cC]$', file['filename']))
        # Apparently new e3 cant handle any filename that endswith '.c'

    async def _get_assign_files(self,
                                token: str,
                                course_dict: Dict[str, str],
                                courses: Iterable[Course]) -> Iterable[E3File]:
        payload = {
            'wsfunction': 'mod_assign_get_assignments',
            'wstoken': token,
        }
        for idx, (courseid, _) in enumerate(courses):
            payload[f'courseids[{idx}]'] = courseid
        resp = await self._session.post(self._api_url, data=payload)
        resp_json = json.loads(await resp.text())
        return (
            E3File(
                file['filename'],
                course_dict[str(course['id'])],
                sha1_hash2(str(assignment['id']), file['filename']),
                file['fileurl'] + "?token=" + token,
                file['timemodified']
            )
            for course in resp_json['courses']
            for assignment in course['assignments']
            for file in assignment['introattachments']
            if not re.match(r'.*\.[cC]$', file['filename']))

    async def login(self,
                    username: str,
                    password: str) -> bool:
        self._session = ClientSession()
        try:
            self.token = await self._get_token(username, password)
        except KeyError:
            await self._session.close()
            return False
        self.userid = await self._get_userid(username, self.token)
        return True

    async def all_files(self) -> AsyncIterable[E3File]:
        if self.token is None:
            raise RuntimeError("Please Login First")
        courses = list(await self.__get_course_list(self.userid, self.token))
        course_dict = dict(courses)
        course_folders = await self._get_folders(self.token, courses)
        futures = [self._get_materials(self.token, course_dict[i.course_id], i)
                   for i in course_folders]
        futures.append(self._get_assign_files(self.token, course_dict, courses))
        for future in asyncio.as_completed(futures):
            files = await future
            for file in files:
                yield file
        await self._session.close()


async def main() -> None:
    new_e3 = NewE3()
    while True:
        username = input('StudentID: ')
        password = getpass('Password: ')
        if await new_e3.login(username, password):
            break
    async for file in new_e3.all_files():
        print(file)


if __name__ == "__main__":
    asyncio.run(main())
