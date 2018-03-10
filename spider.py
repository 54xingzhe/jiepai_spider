import json
import os
from hashlib import md5
from urllib.parse import urlencode
import re
import pymongo
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
from config import *
from multiprocessing import Pool
from json.decoder import JSONDecodeError


client = pymongo.MongoClient(MONGO_URL, connect=False)
db = client[MONGO_DB]

# 获取索引页
def get_page_index(offset, keyword):
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': 20,
        'cur_tab': 3
    }
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)  # urlencode()  此方法可以将字典类对象转化为URL参数，是urllib库提供的编码方法
    try:  # 异常处理
        response = requests.get(url)  #利用request请求URL
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求索引页出错')
        return None

# 解析索引页
def parse_page_index(html):  # 参数是返回的数据
    try:
        data = json.loads(html)  # 用json.loads()方法将json字符串转换成json格式的变量
        if data and 'data' in data.keys():  # data.keys()是返回的json的键名。如果返回data而且data在键名里
            for item in data.get('data'):  # 对data进行遍历
                yield item.get('article_url')  # 通过yield构造生成器，获取到详情页的URL
    except JSONDecodeError:
        pass

# 获取详情页
def get_page_detail(url):
    try:  #处理异常
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求详情页出错', url)
        return None

# 解析详情页
def parse_page_detail(html, url):
    soup = BeautifulSoup(html, 'lxml')  # 用BeautifulSoup获取title
    title = soup.select('title')[0].get_text()
    print(title)
    image_pattern = re.compile('gallery: JSON.parse(.*?);', re.S)
    result = re.search(image_pattern, html)
    if result:  # 判断匹配是否成功
        data = json.loads(result.group(1))  # 用json.loads()方法将json字符串转换成json格式的对象
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            images = [item.get('url') for item in sub_images]
            for image in images:
                download_image(image)  # 获取到images后，将image保存下来
            return {
                'title': title,
                'url': url,
                'images': images
            }

# 存储到数据库
def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):  # 插入数据成功返回true
        print('存储到MongoDB成功', result)
        return True
    return False

# 下载图片
def download_image(url):
    print('正在下载', url)
    try:
        response = requests.get(url)
        if response.status_code == 200:
            save_image(response.content)  # 请求成功的话就将图片保存下来
        return None
    except RequestException:
        print('请求图片出错', url)
        return None

# 保存图片
def save_image(content):
    file_path = '{0}/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')  # 三部分内容是：路径，文件名，后缀。os.getcwd()当前项目路径，md5()方法去重
    if not os.path.exists(file_path):  # 如果路径中没有，就保存下来
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()

def main(offset):
    html = get_page_index(offset, KEYWORD)
    # print(html)
    for url in parse_page_index(html):
        # print(url)  # 遍历获取到的URL，并且打印出来
        html = get_page_detail(url)
        if html:  # 如果成功返回的话，调用解析函数
            result = parse_page_detail(html, url)
            # print(result)
            save_to_mongo(result)

if __name__ == '__main__':
    # main()
    groups = [x * 20 for x in range(GROUP_START, GROUP_END + 1)]
    pool = Pool()
    pool.map(main, groups)
