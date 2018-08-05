import requests
from bs4 import BeautifulSoup
import FileDownloader
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal


class iLearnManager(QWidget):
    signal_finishDownload = pyqtSignal()
    signal_Log = pyqtSignal(str)
    signal_FinishGetCourseResource = pyqtSignal(list)

    def __init__(self, host='http://ilearn2.fcu.edu.tw'):
        super(iLearnManager,self).__init__()
        self.web = requests.Session()
        self.NID = ""
        self.Pass = ""
        self.courseList=[]
        self.host = host

    def print(self,msg):
        self.signal_Log.emit(msg)

    def TestConnection(self):
        self.print('正在測試與iLearn的連線...')
        page = self.web.get(self.host+"/login/index.php")
        html = BeautifulSoup(page.text, 'lxml')
        form_login = html.find('form', id='login')

        if form_login is not None:
            return True
        else:
            return False

    def setUser(self, NID, Password):
        self.NID = NID
        self.Pass = Password

    def Login(self):
        payload = {'username': self.NID, 'password': self.Pass}
        page = self.web.post(self.host+'/login/index.php', data=payload)
        html = BeautifulSoup(page.text, 'html.parser')
        img_userpicture = html.find('img', {'class':'userpicture'})
        if img_userpicture is not None:
            userName = img_userpicture.get('title').split(' ')[1][:-3]
            return True, userName
        else:
            return False, ''

    def getCourseList(self):
        r = self.web.get(self.host)
        soup = BeautifulSoup(r.text, 'html.parser')
        div_course = soup.find_all('div', {"style": "font-size:1.1em;font-weight:bold;line-height:20px;"})
        CourseList = [div.a.attrs for div in div_course if 'class' not in div.a.attrs]
        for ele in CourseList:
            ele['id'] = ele['href'][-5:]
            del ele['href']
        self.courseList = CourseList
        return CourseList

    def getCourseMainResourceList(self, classInfo):
        r = self.web.get(self.host+'/course/view.php?id=' + classInfo['id'])
        soup = BeautifulSoup(r.text, 'html.parser')
        div_main = soup.find_all('ul', {"class": "topics"})[0]
        div_section = div_main.find_all('li',{'role':'region'})
        ResourceList = []
        for section in div_section:
            try:
                section_name = section.find_all('h3', {'class': 'sectionname'})[0].text
            except:
                section_name = section.get('aria-label')
            try:
                UrlList = section.contents[2].ul.contents
            except:
                UrlList = []
            resourceInSection=[]
            for url in UrlList:
                try:
                    url = url.find_all('a')[0]
                    href = url.get('href')
                    mod = href.split('/mod/')[1].split('/view')[0]
                    mod_id = href.split('?id=')[1].split('"')[0]
                    mod_name = url.find_all('span', {'class': 'instancename'})[0]
                    if mod_name.span is not None:
                        mod_name.span.decompose()
                    mod_name = mod_name.text
                    path = classInfo['title'] + '/' + self.removeIllageWord(section_name)
                    resourceInSection.append({'path': path, 'mod': mod, 'mod_id': mod_id, 'name': self.removeIllageWord(mod_name)})
                except:
                    pass
            if len(resourceInSection) != 0:
                ResourceList.append({'name':section_name,'mods':resourceInSection})
        return ResourceList

    def removeIllageWord(self, string):
        for ele in '/\\*|?:"':
            while ele in string:
                string = string.replace(ele, '-')
        while '<' in string:
            string = string.replace(ele, '(')
        while '>' in string:
            string = string.replace(ele, ')')
        return string

    def getCourseFileList(self, classInfo):
        MainResourceList = self.getCourseMainResourceList(classInfo)
        FileList=[]

        for section in MainResourceList:
            recourceList = []
            for recource in section['mods']:
                if recource['mod']=='forum':
                    recource['data']=self.getFileList_forum(recource)
                    recourceList.append(recource)
                if recource['mod']=='resource':
                    recource = self.getFileList_resource(recource)
                    recourceList.append(recource)
                elif recource['mod'] in ['url', 'assign', 'page', 'videos']:
                    recourceList.append(recource)
                elif recource['mod'] == 'folder':
                    recource['data']=self.getFileList_folder(recource)
                    recourceList.append(recource)
                else:
                    self.print('發現不支援的課程模組 '+recource['mod']+' mod: '+recource['name'])
            FileList.append({'section':section['name'],'mods':recourceList})
        return FileList

    def getFileList_forum(self, info):
        FileList = []
        r = self.web.get('https://ilearn2.fcu.edu.tw/mod/forum/view.php?id=' + info['mod_id'])
        soup = BeautifulSoup(r.text, 'lxml')
        folderName = soup.find_all('div',{'role': 'main'})[0].h2.text
        allTopic = soup.find_all('td', {'class': 'topic starter'})
        for topic in allTopic:
            path = info['path'] + '/' + folderName + '/ '+self.removeIllageWord(topic.text)
            mod = 'forum/discuss'
            mod_id = topic.a.get('href').split('d=')[1]
            name = self.removeIllageWord(topic.text)
            FileList.append({'path': path, 'mod': mod, 'mod_id': mod_id, 'name': name})
        return FileList

    def getFileList_resource(self, info):
        r = self.web.get('https://ilearn2.fcu.edu.tw/mod/resource/view.php?id=' + info['mod_id'])
        soup = BeautifulSoup(r.text, 'lxml')
        try:
            filename = soup.find('div',{'class':'resourceworkaround'}).a.text
        except:
            filename = info['name']
        info['name'] = filename
        return info

    def getFileList_folder(self, info):
        return []

    def DownloadFile(self, StatusTable, index, fileInfo):
        if fileInfo['mod'] == 'forum/discuss':
            downloader = FileDownloader.discuss()
        else:
            downloader = FileDownloader.BasicDownloader()
        downloader.setInformation(self.web, fileInfo, StatusTable, index)
        downloader.signal_downloadNextFile.connect(self.finishDownload)
        downloader.signal_errorMsg.connect(self.showErrorMsg)
        downloader.download()

    def finishDownload(self):
        self.signal_finishDownload.emit()

    def showErrorMsg(self, Msg):
        self.print(Msg)
