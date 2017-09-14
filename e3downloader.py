import requests
import re
import urllib.parse
from multiprocessing import Queue
from bs4 import BeautifulSoup

account = input('學號')
pwd = input('密碼')
session = requests.Session()
baseUrl = "http://e3.nctu.edu.tw/NCTU_Easy_E3P/lms3/"
url = "https://dcpc.nctu.edu.tw/index.aspx"
print(url)
r = session.get(url)
print(r.status_code)
soup = BeautifulSoup(r.content, "html.parser")
__VIEWSTATE = soup.find('input', {"name": "__VIEWSTATE"}).get('value')
__VIEWSTATEGENERATOR = soup.find(
    'input', {"name": "__VIEWSTATEGENERATOR"}).get('value')
__EVENTVALIDATION = soup.find(
    'input', {"name": "__EVENTVALIDATION"}).get('value')

data = {"txtAccount": account, "txtPwd": pwd,
        "__VIEWSTATE": __VIEWSTATE,
        "__VIEWSTATEGENERATOR": __VIEWSTATEGENERATOR,
        "__EVENTVALIDATION": __EVENTVALIDATION,
        "__VIEWSTATEENCRYPTED": "",
        "btnLoginIn": "SIGH IN"}

print(url)
r = session.post(url, data=data)
print(r.status_code)

soup = BeautifulSoup(r.content, "html.parser")
__VIEWSTATE = soup.find('input', {"name": "__VIEWSTATE"}).get('value')
__VIEWSTATEGENERATOR = soup.find(
    'input', {"name": "__VIEWSTATEGENERATOR"}).get('value')
content = r.content.decode('utf-8')
content = content[content.find("<!--當期課程 Start-->")
                               :content.find("<!--當期課程 End-->")]
soup = BeautifulSoup(content, "html.parser")
for i in soup.findAll('a', {'class': 'g2'}):
    regex0 = r"javascript:__doPostBack\('([^']*)"
    data = {"__VIEWSTATE": __VIEWSTATE,
            "__VIEWSTATEGENERATOR": __VIEWSTATEGENERATOR,
            "__EVENTTARGET": re.findall(regex0, i['href'])}
    url = baseUrl + "enter_course_index.aspx"
    print(url)
    r = session.post(url, data=data)
    print(r.status_code)

    url = baseUrl + "stu_materials_document_list.aspx"
    print (url)
    r = session.get(url)
    print(r.status_code)
    regex = r"<a[^']*'([^,]*)[^>]*>\[&nbsp;view&nbsp;\]"
    content = r.content.decode('utf-8')
    for j in re.findall(regex, content):
        url = "http://e3.nctu.edu.tw/NCTU_EASY_E3P/LMS3/" + j
        print(url)
        r2 = session.get(url)
        print(r2.status_code)
        content2 = r2.content.decode('utf-8')
        regex2 = r"openDialog_hWin_[a-z0-9]*\('([^,]*)"
        try:
            url = "http://e3.nctu.edu.tw/NCTU_EASY_E3P/LMS3/" +  re.findall(regex2, content2)[1]
        except IndexError:
            continue
        print(url)
        r3 = session.get(url)
        print('r3')
        print(r3.status_code)
        soup = BeautifulSoup(r3.content, "html.parser")
        url = "http://e3.nctu.edu.tw/NCTU_EASY_E3P/LMS3/" + \
            soup.find('a')['href']
        print(url)
        r4 = session.get(url, stream=True)
        print(r4.status_code)
        try:
            fileName = r4.headers['Content-Disposition']
        except KeyError:
            continue
        fileName = fileName[fileName.find('=') + 1:]
        fileName = urllib.parse.unquote(fileName)
        print (fileName)
        with open(fileName, 'wb') as f:
            for chunk in r4.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
