import json
import os
import re
from _md5 import md5
from json import JSONDecodeError
from urllib.parse import urlencode

import pymongo
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
import requests
from config import *
# 引入多线程 下面是进程池
from  multiprocessing import Pool

client =pymongo.MongoClient(MONGO_URL,connect=False)
db = client[MONGO_DB]

def get_page_index(offset,keyword):
    data ={
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': 20,
        'cur_tab': 3
    }
    url ='http://www.toutiao.com/search/?'+ urlencode(data)
    print('([%d] 正在下载索引页 %s' % (os.getpid(), url))
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求失败')
        return None


# 对jsons数据进行解析
def parse_page_index(html):
    try:
        data = json.loads(html)
        if data and 'data' in data.keys():
            for item in data.get('data'):
                # 用 yield构造生成器
                yield item.get('article_url')
    except JSONDecodeError:
        print(111)

def get_page_detail(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return  response.text
        return  None
    except RequestException:
        print('请求详情页出错',url)
        return None
def parse_page_detail(html,url):
    soup=BeautifulSoup(html,'lxml')
    title =soup.select('title')[0].get_txt()
    images_pattern=re.compile( 'var gallery =(.*?);',re.S)
    result = re.search(images_pattern,html)
    if result:
        data = json.loads(result.group(1))
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            images =[item.get('url')for item in sub_images]
            for image in images: download_image(image)
            return {
                    'title': title,
                    'url':url,
                    'images':images
                }
        print(result.group(1))
def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储到 MongoDB成功',result)
        return  True
    return False
def download_image(url):
    print('当前正在下载那一张图片',url)
    try:
        respose =requests.get(url)
        if respose.status_code ==200:
            # content是二进制内容 text是正常网页结果
            save_image(respose.content)
            return respose.text
        return None
    except RequestException:
        print('请求图片出错',url)
        return None
def save_image(content):
    # 存储文件路径 由三部分组成 路径，文件名，后缀  md5 方法判断内容不一致
    file_path = '{0}/{1}.{2}'.format(os.getcwd(),md5(content).hexdigest(),'jpg')
    if not os.path.exists(file_path):
        with open(file_path,'wb')as f:
            f.write(content)
            f.close()
def main(offset):
    html = get_page_index(offset,KEYWORD)
    for url in parse_page_index(html):
        html = get_page_index(url)
        if html:
           result= parse_page_detail(html,url)
           save_to_mongo(result)


if __name__=='__main__':
    groups =[x*20 for x in range(GROUP_START,GROUP_END)]
    # 声明进程池
    pool=Pool()
    # 开启多线程 第一个是要执行的目标元素，第二个是集合就是当前的list
    pool.map(main,groups)