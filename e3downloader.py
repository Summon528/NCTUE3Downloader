import requests
import xml.etree.ElementTree
import urllib
import os
import datetime
import sys
from multiprocessing import Queue

BASE_URL = "http://e3.nctu.edu.tw/mService/service.asmx/"
HEADERS = {
    'content-type': 'application/x-www-form-urlencoded',
}

try:
    ACCOUNT = sys.argv[1]
    PASSWORD = sys.argv[2]
except IndexError:
    ACCOUNT = input('學號 ')
    PASSWORD = input('密碼 ')

while True:
    try:
        data = {"account": ACCOUNT, "password": PASSWORD}
        r = requests.post(BASE_URL + 'Login', data=data, headers=HEADERS)
        root = xml.etree.ElementTree.fromstring(r.content)
        LoginTicket = root[0].text
        AccountId = root[1].text
        print("Login Success")
        break
    except:
        print("Login Fail")
        ACCOUNT = input('學號 ')
        PASSWORD = input('密碼 ')
        continue

try:
    f = open('lastTime.txt', 'r')
    try:
        lastTime = datetime.datetime.strptime(f.read(), '%Y/%m/%d %H:%M:%S')
        print("last run:" + datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
    except:
        print("lastTime.txt is corrupted.")
        lastTime = datetime.datetime(1970, 1, 1, 0, 0, 0)
    f.close()
except FileNotFoundError:
    print("Download all files.")
    lastTime = datetime.datetime(1970, 1, 1, 0, 0, 0)

programStartTime = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")

data = {"loginTicket": LoginTicket, "accountId": AccountId, 'role': 'stu'}
r = requests.post(BASE_URL + 'GetCourseList', data=data, headers=HEADERS)
root = xml.etree.ElementTree.fromstring(r.content)
CourseId = []
CourseName = []
for i in root:
    CourseId.append(i[0].text)
    CourseName.append(i[3].text)


for i in range(len(CourseId)):
    print(CourseName[i])
    print('課程講義')
    try:
        os.mkdir(CourseName[i])
    except FileExistsError:
        pass
    try:
        os.mkdir(os.path.join(CourseName[i], '課程講義'))
    except FileExistsError:
        pass
    data = {"loginTicket": LoginTicket,
            "courseId": CourseId[i], 'docType': '1'}
    r = requests.post(BASE_URL + 'GetMaterialDocList',
                      data=data, headers=HEADERS)
    root = xml.etree.ElementTree.fromstring(r.content)
    DisplayName = []
    DocumentId = []
    for j in root:
        DisplayName.append(j[2].text)
        DocumentId.append(j[11].text)
    for j in DocumentId:
        data = {"loginTicket": LoginTicket, "resId": j,
                'metaType': '10', 'courseId': CourseId[i]}
        r = requests.post(BASE_URL + 'GetAttachFileList',
                          data=data, headers=HEADERS)
        root = xml.etree.ElementTree.fromstring(r.content)

        for k in root:
            fileTime = datetime.datetime.strptime(
                k[8].text, '%Y/%m/%d %H:%M:%S')
            print(k[3].text)
            if fileTime >= lastTime:
                r2 = requests.get(k[4].text, stream=True)
                try:
                    fileName = r2.headers['Content-Disposition']
                except KeyError:
                    continue
                fileName = fileName.encode('latin-1').decode('utf-8', 'ignore')
                fileName = fileName[fileName.find(
                    '=') + 2:fileName.find(',') - 1]
                fileName = urllib.parse.unquote(fileName)
                segment = int(r2.headers['content-length']) // 80
                cnt = 0
                with open(os.path.join(CourseName[i], '課程講義', fileName), 'wb') as f:
                    sum = 0
                    for chunk in r2.iter_content(chunk_size=1024):
                        if sum > segment * cnt:
                            cnt += 1
                            print('#', end='', flush=True)
                            if segment < 1024:
                                for k in range(((sum - (segment * cnt)) // segment)):
                                    cnt += 1
                                    print('#', end='', flush=True)
                        sum += 1024
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
                print('')
            else:
                print("skip")

    print('參考資料')
    try:
        os.mkdir(os.path.join(CourseName[i], '參考資料'))
    except FileExistsError:
        pass
    data = {"loginTicket": LoginTicket,
            "courseId": CourseId[i], 'docType': '1'}
    r = requests.post(BASE_URL + 'GetMaterialDocList',
                      data=data, headers=HEADERS)
    root = xml.etree.ElementTree.fromstring(r.content)
    DisplayName = []
    DocumentId = []
    for j in root:
        DisplayName.append(j[2].text)
        DocumentId.append(j[11].text)
    for j in DocumentId:
        data = {"loginTicket": LoginTicket, "resId": j,
                'metaType': '10', 'courseId': CourseId[i]}
        r = requests.post(BASE_URL + 'GetAttachFileList',
                          data=data, headers=HEADERS)
        root = xml.etree.ElementTree.fromstring(r.content)
        for k in root:
            fileTime = datetime.datetime.strptime(
                k[8].text, '%Y/%m/%d %H:%M:%S')
            print(k[3].text)
            if fileTime >= lastTime:
                r2 = requests.get(k[4].text, stream=True)
                try:
                    fileName = r2.headers['Content-Disposition']
                except KeyError:
                    continue
                fileName = fileName.encode('latin-1').decode('utf-8')
                fileName = fileName[fileName.find(
                    '=') + 2:fileName.find(',') - 1]
                fileName = urllib.parse.unquote(fileName)
                segment = int(r2.headers['content-length']) // 80
                cnt = 0
                with open(os.path.join(CourseName[i], '參考資料', fileName), 'wb') as f:
                    sum = 0
                    for chunk in r2.iter_content(chunk_size=1024):
                        if sum > segment * cnt:
                            cnt += 1
                            print('#', end='', flush=True)
                            if segment < 1024:
                                for k in range(((sum - (segment * cnt)) // segment)):
                                    cnt += 1
                                    print('#', end='', flush=True)
                        sum += 1024
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
                    print('')

            else:
                print('skip')

    print('作業')
    try:
        os.mkdir(os.path.join(CourseName[i], '作業'))
    except FileExistsError:
        pass
    data = {"loginTicket": LoginTicket,
            "courseId": CourseId[i], "accountId": AccountId, 'listType': 1}
    r = requests.post(BASE_URL + 'GetStuHomeworkListWithAttach',
                      data=data, headers=HEADERS)
    root = xml.etree.ElementTree.fromstring(r.content)
    if len(root) > 0:
        for j in root[0][25]:
            r2 = requests.get(j.text[:-1], stream=True)
            try:
                fileName = r2.headers['Content-Disposition']
            except KeyError:
                continue
            fileName = fileName.encode('latin-1').decode('utf-8')
            fileName = fileName[fileName.find(
                '=') + 2:fileName.find(',') - 1]
            fileName = urllib.parse.unquote(fileName)
            print(fileName)
            segment = int(r2.headers['content-length']) // 80
            cnt = 0
            if os.path.isfile(os.path.join(CourseName[i], '作業', fileName)) == False:
                with open(os.path.join(CourseName[i], '作業', fileName), 'wb') as f:
                    sum = 0
                    for chunk in r2.iter_content(chunk_size=1024):
                        if sum > segment * cnt:
                            cnt += 1
                            print('#', end='', flush=True)
                        if segment < 1024:
                            for k in range(((sum - (segment * cnt)) // segment)):
                                cnt += 1
                                print('#', end='', flush=True)
                        sum += 1024
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
                    print('')
            else:
                print('skip')
    print('')
f = open('lastTime.txt', 'w')
f.write(datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
f.close()
