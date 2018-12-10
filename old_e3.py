import re
import json
import hashlib
import asyncio
from getpass import getpass
from datetime import datetime
from typing import Iterable, NamedTuple, AsyncIterable
from aiostream import stream
from bs4 import BeautifulSoup
from models import Course, E3File, FolderType
from asp_session import ASPSession


class OldE3():

    class FolderProperty(NamedTuple):
        folder_type: FolderType
        table_el_id: str
        event_target: str
        json_key: str
        data_navigator_el_id: str

    def __init__(self):
        self.__url = 'https://e3.nctu.edu.tw/NCTU_Easy_E3P/lms31'
        self.__folder_properties = [
            self.FolderProperty(
                FolderType.HANDOUT,
                "ctl00_ContentPlaceHolder1_dgCourseHandout",
                "ctl00$ContentPlaceHolder1$DataNavigator1$ctl03",
                "ctl00$ContentPlaceHolder1$dgCourseHandout",
                "ctl00_ContentPlaceHolder1_DataNavigator1_ctl02"
            ),
            self.FolderProperty(
                FolderType.REFERENCE,
                "ctl00_ContentPlaceHolder1_dgCourseReference",
                "ctl00$ContentPlaceHolder1$DataNavigator3$ctl03",
                "ctl00$ContentPlaceHolder1$dgCourseReference",
                "ctl00_ContentPlaceHolder1_DataNavigator3_ctl02"
            )
        ]

    async def login(self,
                    session: ASPSession,
                    username: str,
                    password: str) -> None:
        await session.get(self.__url+'/login.aspx')
        await session.post(self.__url+'/login.aspx', data={
            'txtLoginId': username,
            'txtLoginPwd': password,
            'btnLogin.x': '0',
            'btnLogin.y': '0',
        })

    async def __get_course_list(self,
                                session: ASPSession) -> Iterable[Course]:
        soup = await session.get(self.__url+'/enter_course_index.aspx')
        return (Course(el['id'].replace('_', '$'), el.text)
                for el in soup.find(id='ctl00_ContentPlaceHolder1_gvCourse')('a'))

    async def __to_course_page(self,
                               session: ASPSession,
                               course: Course) -> None:
        await session.post(self.__url+'/enter_course_index.aspx', data={
            '__EVENTTARGET': course.course_id
        })

    def __parse_folder_table(
            self,
            soup: BeautifulSoup,
            folder_property: FolderProperty,
            course: Course) -> Iterable[E3File]:
        table_el = soup.find(id=folder_property.table_el_id)
        tr_els = table_el('tr')[1:]
        for tr_el in tr_els:
            td_els = tr_el('td')
            files = td_els[1]('a')
            for file in files:
                matched = re.search(
                    r"AttachMediaId=([^;,']*).*CourseId=([^;,']*)", file['onclick'])
                if matched:
                    yield E3File(
                        file.text,
                        course.course_name,
                        hashlib.sha1(matched.group(1).encode()).hexdigest(),
                        self.__url +
                        f'/common_view_standalone_file.ashx?AttachMediaId={matched.group(1)}'
                        f'&CourseId={matched.group(2)}',
                        int(datetime.strptime(
                            td_els[2].text, '%Y/%m/%d').timestamp())
                    )

    async def __get_materials(self,
                              session: ASPSession,
                              course: Course) -> AsyncIterable[E3File]:
        soup = await session.get(self.__url+'/stu_materials_document_list.aspx')
        for folder_property in self.__folder_properties:
            data_navigator_text = soup.find(
                id=folder_property.data_navigator_el_id).text
            matched = re.search(r'共\xa0(\d*)\xa0頁', data_navigator_text)
            if matched:
                total_page = int(matched.group(1))
                for file in self.__parse_folder_table(soup, folder_property, course):
                    yield file
                for _ in range(total_page-1):
                    for file in await self.__get_remaining_materials(session, folder_property, course):
                        yield file

    async def __get_remaining_materials(self,
                                        session: ASPSession,
                                        folder_property: FolderProperty,
                                        course: Course) -> Iterable[E3File]:
        resp = await session.post(
            self.__url+'/stu_materials_document_list.aspx?Anthem_CallBack=true', data={
                'Anthem_UpdatePage': 'true',
                '__EVENTTARGET': folder_property.event_target,
                'ctl00$ContentPlaceHolder1$EasyView': 'rdoView1',
                f'{folder_property.event_target}.x': '0',
                f'{folder_property.event_target}.y': '0'
            })
        resp_json = json.loads(await resp.text())['controls'][folder_property.json_key]
        soup = BeautifulSoup(resp_json, 'html.parser')
        return self.__parse_folder_table(soup, folder_property, course)

    async def __get_assign_files(self,
                                 session: ASPSession,
                                 course: Course) -> AsyncIterable[E3File]:
        soup = await session.get(self.__url+'/stu_materials_homework_list.aspx')
        for table_el_id in ['ctl00_ContentPlaceHolder1_dgHandin',
                            'ctl00_ContentPlaceHolder1_dgJudge',
                            'ctl00_ContentPlaceHolder1_dgLate',
                            'ctl00_ContentPlaceHolder1_dgAlready']:
            table_el = soup.find(id=table_el_id)
            if table_el:
                futures = []
                for el in table_el('tr')[1:]:
                    td_els = el('td')
                    assign_id = re.search(r"crsHwkId=([^;,']*)",  # type: ignore
                                          td_els[-1]('a')[0]['onclick']).group(1)
                    futures.append(
                        self.__get_assign_detail(
                            session,
                            assign_id,
                            course)
                    )
                for future in asyncio.as_completed(futures):
                    files = await future
                    for file in files:
                        yield file

    async def __get_assign_detail(self,
                                  session: ASPSession,
                                  assign_id: str,
                                  course: Course) -> Iterable[E3File]:
        resp = await session.post(self.__url+'/ajaxpro/WebPageBase,App_Code.ashx', headers={
            'X-AjaxPro-Method': 'setToken'
        })
        token = json.loads(await resp.text())['value']
        soup = await session.get(self.__url +
                                 f'/dialog_stu_homework_view.aspx?crsHwkId={assign_id}&TokenId={token}')
        files = soup.find(
            id='Anthem_ctl00_ContentPlaceHolder1_HwkInfo1_fileAttachManageLite_rpFileList__')

        def gen():
            if files:
                for file in files('a'):
                    file_id = re.search(
                        r"AttachMediaId=([^;,'&]*)", file['href']).group(1)
                    file_url = self.__url+file['href'].replace('common_get_content_media_attach_file.ashx',
                                                               '/common_view_standalone_file.ashx')
                    yield E3File(
                        file.text,
                        course.course_name,
                        hashlib.sha1(file_id.encode()).hexdigest(),
                        file_url,
                        1
                    )
        return gen()

    async def __get_course_all_files(self,
                                     username: str,
                                     password: str,
                                     course: Course,
                                     session: ASPSession = None) -> AsyncIterable[E3File]:
        if not session:
            session = ASPSession()
            await self.login(session, username, password)
            await session.get(self.__url+'/enter_course_index.aspx')
        await self.__to_course_page(session, course)
        files = self.__get_materials(session, course)
        async for file in files:
            yield file
        files = self.__get_assign_files(session, course)
        async for file in files:
            yield file
        await session.close()

    async def all_files(self,
                        username: str,
                        password: str) -> AsyncIterable[E3File]:
        session = ASPSession()
        await self.login(session, username, password)
        courses = list(await self.__get_course_list(session))
        gens = [self.__get_course_all_files(username, password, course)
                for course in courses[:-1]]
        gens.append(self.__get_course_all_files(
            username, password, courses[-1], session))
        async with stream.merge(*gens).stream() as files:
            async for file in files:
                yield file


async def main():
    old_e3 = OldE3()
    username = input('StudentID: ')
    password = getpass('Password: ')
    async for file in old_e3.all_files(username, password):
        print(file)


if __name__ == "__main__":
    asyncio.run(main())
