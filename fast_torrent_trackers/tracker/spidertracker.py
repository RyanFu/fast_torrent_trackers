import asyncio
import logging
import random
import re
from http.cookies import SimpleCookie

import aiofiles
import httpx
from bs4 import BeautifulSoup
from httpx import Timeout
from jinja2 import Template
from pyrate_limiter import Limiter, RequestRate, Duration
from tenacity import retry, stop_after_delay, wait_exponential

from fast_torrent_trackers.basetracker import BaseTracker, user_agent_rotator
from fast_torrent_trackers.exceptions import LoginRequired, RequestOverloadException, RateLimitException
from fast_torrent_trackers.htmlparser import HtmlParser
from fast_torrent_trackers.resultfilters import result_filters
from fast_torrent_trackers.models import TrackerUserinfo, TorrentList, TorrentInfo
from fast_torrent_trackers.utils import trans_size_str_to_mb

_LOGGER = logging.getLogger(__name__)
download_limiter = Limiter(RequestRate(1, 15 * Duration.SECOND))


class TrackerParser:
    def __init__(self, site_config):
        self.site_config = site_config

    def test_login(self, html_text):
        if not html_text:
            return False
        login_config = self.site_config.get('login')
        if not login_config:
            return
        test = login_config.get('test')
        soup = BeautifulSoup(html_text, 'lxml')
        tag = soup.select_one(test.get('selector'))
        if tag:
            return True
        else:
            return False

    def parse_userinfo(self, html_text):
        if not self.test_login(html_text):
            raise LoginRequired(self.site_config.get('id'), self.site_config.get('name'),
                                f'{self.site_config.get("name")}登陆失败！')
        user_rule = self.site_config.get('userinfo')
        if not user_rule:
            return
        field_rule = user_rule.get('fields')
        if not field_rule:
            return
        soup = BeautifulSoup(html_text, 'lxml')
        item_tag = soup.select_one(user_rule.get('item')['selector'])
        result = HtmlParser.parse_item_fields(item_tag, field_rule)
        return result

    def parse_torrents(self, html_text, context=None) -> TorrentList:
        torrents_rule = self.site_config.get('torrents')
        if not torrents_rule:
            return []
        list_rule = torrents_rule.get('list')
        fields_rule = torrents_rule.get('fields')
        if not fields_rule:
            return []
        soup = BeautifulSoup(html_text, 'lxml')
        rows = soup.select(list_rule['selector'])
        if not rows:
            return []
        result: TorrentList = []
        for tag in rows:
            item = HtmlParser.parse_item_fields(tag, fields_rule, context=context)
            result.append(TorrentInfo.build_by_parse_item(self.site_config, item))
        return result


class SpiderTracker(BaseTracker):
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36'}
    cookies = None
    last_search_text = None
    userinfo = None

    def __init__(self, site_config, cookie_str=None, request_timeout=10.0, download_timeout=180.0, proxies=None,
                 user_agent=None):
        self.request_timeout = request_timeout
        self.download_timeout = download_timeout
        self.set_cookie(cookie_str)
        self.site_config = site_config
        self.parser = TrackerParser(site_config)
        self.category_mappings = self._init_category_mappings(site_config.get('category_mappings'))
        self.search_paths = self.__init_search_paths__(site_config.get('search').get('paths'), self.category_mappings)
        self.search_query = self.__init_search_query__(site_config.get('search').get('query'))
        if proxies:
            self.proxies = proxies
        else:
            self.proxies = None
        if user_agent:
            self.headers['user-agent'] = user_agent
        else:
            self.headers['user-agent'] = user_agent_rotator.get_random_user_agent()

    def set_cookie(self, cookie_str: str):
        if not cookie_str:
            return
        cookie = SimpleCookie(cookie_str)
        cookies = {}
        for key, morsel in cookie.items():
            cookies[key] = morsel.value
        self.cookies = cookies

    def __render_querystring__(self, query):
        qs = ''
        for key in self.search_query:
            val = self.search_query[key]
            if isinstance(val, Template):
                val = val.render({'query': query})
            if key == '$raw' and val is not None and val != '':
                qs += val
            elif val is not None and val != '':
                qs += f'{key}={val}&'
        if qs:
            qs = qs.rstrip('&')
        return qs

    @staticmethod
    def __init_search_paths__(paths_config, category_mappings):
        paths = []
        for p in paths_config:
            obj: dict = dict()
            obj['path'] = p.get('path')
            cate_ids_config = p.get('categories')
            search_cate_ids = []
            if cate_ids_config:
                # 如果可用id第一个字符为!，则说明是排除设置模式
                if cate_ids_config[0] == '!':
                    for c in category_mappings:
                        if (int(c['id']) if c['id'] else 0) not in cate_ids_config:
                            search_cate_ids.append(str(c['id']))
                else:
                    search_cate_ids = [str(c) for c in cate_ids_config]
            else:
                search_cate_ids = [str(c['id']) for c in category_mappings]
            obj['categories'] = search_cate_ids
            if p.get('method'):
                obj['method'] = p.get('method')
            else:
                obj['method'] = 'get'
            paths.append(obj)
        return paths

    @staticmethod
    def __init_search_query__(query_config):
        query_tmpl = {}
        for key in query_config:
            val = query_config[key]
            if isinstance(val, str) and val.find('{') != -1:
                query_tmpl[key] = Template(val)
            else:
                query_tmpl[key] = val
        return query_tmpl

    def __update_cookie__(self, r):
        if not r:
            return
        if r.cookies:
            for k in r.cookies:
                self.cookies[k] = r.cookies[k]

    async def handle_cf_check(self, res):
        if res.text.find('data-cf-settings') != -1 and res.text.find('rocket-loader') != -1:
            match_js_var = re.search(r'window.location=(.+);', res.text)
            if match_js_var:
                check_uri = eval(match_js_var.group(1))
                async with httpx.AsyncClient(
                        headers=self.headers,
                        cookies=self.cookies,
                        follow_redirects=True,
                        timeout=Timeout(timeout=self.request_timeout),
                        proxies=self.proxies
                ) as client:
                    r = await client.get(self.get_domain() + check_uri)
                    self.__update_cookie__(r)
                return self._get_response_text(r)
        elif res.status_code == 503 and res.text.find('<title>Just a moment...</title>') != -1:
            logging.error(f'{self.get_name()}检测到CloudFlare 5秒盾，请浏览器访问跳过拿到新Cookie重新配置。')
            raise LoginRequired(self.get_id(), self.get_name(),
                                f'{self.get_name()}检测到CloudFlare 5秒盾，登陆失败，请浏览器访问重新获取Cookie！')
        self.__update_cookie__(res)
        return self._get_response_text(res)

    @retry(stop=stop_after_delay(600), wait=wait_exponential(multiplier=1, min=30, max=120))
    async def get_userinfo_page_text(self):
        url = self.site_config.get('userinfo').get('path')
        async with httpx.AsyncClient(
                headers=self.headers,
                cookies=self.cookies,
                http2=False,
                timeout=Timeout(timeout=self.request_timeout),
                proxies=self.proxies,
                follow_redirects=True
        ) as client:
            r = await client.get(url)
            text = await self.handle_cf_check(r)
            return text

    @staticmethod
    def trans_to_userinfo(result: dict):
        user = TrackerUserinfo()
        user.uid = int(result['uid'])
        user.username = result['username']
        user.user_group = result['user_group']
        user.uploaded = trans_size_str_to_mb(str(result['uploaded']))
        user.downloaded = trans_size_str_to_mb(str(result['downloaded']))
        try:
            user.seeding = int(result['seeding'])
        except Exception as e:
            user.seeding = 0
        try:
            user.leeching = int(result['leeching'])
        except Exception as e:
            user.leeching = 0
        try:
            if 'share_ratio' in result:
                ss = result['share_ratio'].replace(',', '')
                user.share_ratio = float(ss)
            else:
                if not user.downloaded:
                    user.share_ratio = float('inf')
                else:
                    user.share_ratio = round(user.uploaded / user.downloaded, 2)
        except Exception as e:
            user.share_ratio = 0.0
        user.vip_group = result['vip_group']
        return user

    async def get_userinfo(self, refresh=False) -> TrackerUserinfo:
        if not refresh and self.last_search_text:
            # 用上次搜索结果页内容做解析
            text = self.last_search_text
        else:
            text = await self.get_userinfo_page_text()
        res = self.parser.parse_userinfo(text)
        self.userinfo = res
        return self.trans_to_userinfo(res)

    async def search(self, keyword=None, imdb_id=None, cate_level1_list: list = None, free: bool = False,
                     page: int = None,
                     timeout=None) -> TorrentList:
        if not self.search_paths:
            return []
        input_cate2_ids = set(self._get_cate_level2_ids(cate_level1_list))
        paths = []
        # 根据传入一级分类数据，查找真正要执行的搜索path，一级对应分类
        for p in self.search_paths:
            cpath = p.copy()
            cate_in = list(set(cpath['categories']).intersection(input_cate2_ids))
            if not cate_in:
                continue
            del cpath['categories']
            if len(cate_in) == len(self.category_mappings):
                # 如果等于全部，不需要传分类
                cpath['query_cates'] = []
            else:
                cpath['query_cates'] = cate_in
            paths.append(cpath)
        if len(paths) == 0:
            # 配置文件的分类设置有问题或者真的不存在此分类
            return
        query = {}
        if keyword:
            query['keyword'] = keyword
        if imdb_id:
            query['imdb_id'] = imdb_id
        if free:
            query['free'] = free
        else:
            query['cates'] = []
        if page:
            query['page'] = page
        search_result: TorrentList = []
        if not timeout:
            timeout = self.request_timeout
        for i, p in enumerate(paths):
            if p.get('query_cates'):
                query['cates'] = self._trans_search_cate_id(p.get('query_cates'))
            uri = p.get('path')
            qs = self.__render_querystring__(query)
            headers = self.headers
            headers['Referer'] = f'{self.get_domain()}{uri}'
            async with httpx.AsyncClient(
                    headers=headers,
                    cookies=self.cookies,
                    timeout=Timeout(timeout, connect=60, read=60),
                    proxies=self.proxies,
                    follow_redirects=True
            ) as client:
                if p.get('method') == 'get':
                    url = f'{self.get_domain()}{uri}?{qs}'
                    r = await client.get(url)
                else:
                    url = f'{self.get_domain()}{uri}'
                    r = await client.post(url, data=qs)
                text = await self.handle_cf_check(r)
                if not text:
                    continue
                if text.find('负载过高，120秒后自动刷新') != -1:
                    raise RequestOverloadException('负载过高，120秒后自动刷新', self.get_id(), self.get_name(), 120)
                self.last_search_text = text
                if not self.userinfo:
                    self.userinfo = self.parser.parse_userinfo(text)
                torrents = self.parser.parse_torrents(text, context={'userinfo': self.userinfo})
                if self.site_config.get('search').get('result_filter'):
                    client.cookies = self.cookies
                    r = await result_filters[self.site_config.get('search').get('result_filter')](client, text,
                                                                                                  torrents)
                    self.__update_cookie__(r)
                if torrents:
                    search_result += torrents
            if i + 1 < len(paths):
                # 多页面搜索随机延迟
                await asyncio.sleep(random.randint(3, 5))
        return search_result

    def __check_limit__(self, text, err_msg):
        if not text:
            return
        if text.find('请求次数过多') != -1:
            raise RateLimitException(f'{self.get_name()}{err_msg}')

    @retry(stop=stop_after_delay(300), wait=wait_exponential(multiplier=1, min=30, max=120), reraise=True)
    async def download(self, url, filepath):
        async with download_limiter.ratelimit(self.get_id(), delay=True):
            async with httpx.AsyncClient(
                    headers=self.headers,
                    cookies=self.cookies,
                    timeout=Timeout(timeout=self.download_timeout),
                    proxies=self.proxies,
                    follow_redirects=True
            ) as client:
                if self.get_download_method() == 'POST':
                    if self.get_download_content_type():
                        headers = self.headers
                        headers['content-type'] = self.get_download_content_type()
                        r = await client.post(url, data=self.get_download_args(), headers=headers)
                    else:
                        r = await client.post(url, data=self.get_download_args())
                else:
                    r = await client.get(url)
                if r.status_code == 404:
                    _LOGGER.error(f'Not found torrent: {url}')
                    return
                if 'content-type' in r.headers and r.headers['content-type'].find('text/html') != -1:
                    if r.text.find(
                            '下载提示') != -1 or r.text.find('下載輔助說明') != -1:
                        match_id = re.search(r'name="id"\s+value="(\d+)"', r.text)
                        if match_id:
                            r = await client.post(f'{self.get_domain()}downloadnotice.php',
                                                  data={'id': match_id.group(1), 'type': 'ratio'})
                        else:
                            raise RuntimeError('%s下载种子需要页面确认，先手动打开浏览器下载一次，并重新换Cookie！' % self.get_name())
                    else:
                        self.__check_limit__(r.text, '下载频率过高：%s' % url)
                        logging.error(f'下载种子错误：%s' % url)
                        logging.error('%s' % r.text)
                        raise RuntimeError(f'{self.get_name()}下载出错')
                if r.status_code == 404:
                    return
                async with aiofiles.open(filepath, 'wb') as file:
                    await file.write(r.content)
