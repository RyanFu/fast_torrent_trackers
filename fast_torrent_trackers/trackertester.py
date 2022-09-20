import datetime
import os.path
import time

import yaml

from fast_torrent_trackers.tracker.spidertracker import SpiderTracker
from fast_torrent_trackers.models import TorrentInfo, CateLevel1


class TrackerTester:
    def __init__(self, filepath, cookie_str):
        with open(filepath, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        self.config = config
        print('开始检查站点配置文件')
        self.test_config(self.config)
        self.cookie_str = cookie_str
        self.helper = SpiderTracker(self.config, cookie_str=self.cookie_str)
        print('已经初始化站点配置 id: %s name: %s' % (self.helper.get_id(), self.helper.get_name()))

    async def start_test(self):
        print('开始检查站点登陆有效性')
        await self.test_login()
        print('登陆成功')
        print('开始验证用户信息详细字段数据')
        await self.test_get_userinfo()
        print('用户信息详细字段数据验证成功')
        await self.test_search()
        print('所有测试全部通过！')

    @staticmethod
    def test_config(config):
        for key in ['id', 'name', 'domain', 'encoding', 'login', 'category_mappings', 'userinfo', 'search', 'torrents']:
            if key not in config:
                raise RuntimeError('缺少必要的配置项：%s' % key)

    async def test_login(self):
        test = self.helper.parser.test_login(await self.helper.get_userinfo_page_text())
        if test:
            print('站点登陆成功')
        else:
            raise RuntimeError('站点登陆失败！')

    @staticmethod
    def check_int(name, value, not_zero=False):
        if value is None:
            raise RuntimeError('%s为空' % name)
        if not isinstance(value, int):
            raise RuntimeError('%s类型不是int：%s' % (name, value))
        if value < 0:
            raise RuntimeError('%s数值不应该小于0' % name)
        if not_zero and value == 0:
            raise RuntimeError('%s数值不应该等于0' % name)

    @staticmethod
    def check_str(name, value, not_empty_str=True):
        if value is None or (not_empty_str and value.strip() == ''):
            raise RuntimeError('%s为空' % name)
        if not isinstance(value, str):
            raise RuntimeError('%s类型不是str：%s' % (name, value))

    @staticmethod
    def check_float(name, value, not_zero=False):
        if value is None:
            raise RuntimeError('%s为空' % name)
        if not isinstance(value, float):
            raise RuntimeError('%s类型不是float：%s' % (name, value))
        if value < 0:
            raise RuntimeError('%s数值不应该小于0' % name)
        if not_zero and value == 0:
            raise RuntimeError('%s数值不应该等于0' % name)

    @staticmethod
    def check_bool(name, value):
        if value is None:
            raise RuntimeError('%s为空' % name)
        if not isinstance(value, bool):
            raise RuntimeError('%s类型不是bool：%s' % (name, value))

    async def test_get_userinfo(self):
        userinfo = await self.helper.get_userinfo()
        if not userinfo:
            raise RuntimeError('无法获取用户信息')
        self.check_int('uid', userinfo.uid, not_zero=True)
        self.check_str('username', userinfo.username)
        self.check_float('uploaded', userinfo.uploaded)
        self.check_float('downloaded', userinfo.downloaded)
        self.check_int('seeding', userinfo.seeding)
        self.check_int('leeching', userinfo.leeching)
        self.check_int('vip_group', userinfo.vip_group)

    @staticmethod
    def check_list(value, keyword):
        if not value:
            raise RuntimeError('%s的搜索结果为空' % keyword)
        if not isinstance(value, list):
            raise RuntimeError('%s的搜索结果类型不是list：%s' % (keyword, value))

    @staticmethod
    def check_datetime(name, value):
        if not value:
            raise RuntimeError('%s的值为空' % name)
        if not isinstance(value, datetime.datetime):
            raise RuntimeError('%s的类型不是datetime：%s' % (name, value))

    def test_torrent(self, t: TorrentInfo):
        if not t:
            raise RuntimeError('种子为空')
        self.check_int('torrent.id', t.id, True)
        self.check_str('torrent.site_id', t.site_id)
        self.check_str('torrent.name', t.name)
        self.check_str('torrent.subject', t.subject, not_empty_str=False)
        self.check_float('torrent.size_mb', t.size_mb, True)
        self.check_str('torrent.details_url', t.details_url)
        if t.details_url:
            if not t.details_url.startswith(self.helper.get_domain()):
                raise RuntimeError('details_url没有包含站点链接')
        self.check_str('torrent.download_url', t.download_url)
        if t.download_url:
            if not t.download_url.startswith(self.helper.get_domain()):
                raise RuntimeError('download_url没有包含站点链接')
        self.check_int('torrent.upload_volume_factor', t.upload_volume_factor)
        self.check_float('torrent.download_volume_factor', t.download_volume_factor)
        self.check_int('torrent.download_count', t.download_count)
        self.check_int('torrent.downloading_count', t.downloading_count)
        self.check_int('torrent.upload_count', t.upload_count)
        self.check_datetime('publish_date', t.publish_date)
        if t.download_volume_factor == 0:
            self.check_datetime('free_deadline', t.free_deadline)
        if t.imdb_id is not None:
            if not t.imdb_id.startswith('tt'):
                raise RuntimeError('imdb_id的前缀由tt开始')
        self.check_str('torrent.cate_id', t.cate_id)
        if t.cate_id not in [c['id'] for c in self.helper.category_mappings]:
            raise RuntimeError('cate_id的值未在站点描述配置中存在：%s' % t.cate_id)
        if t.cate_level1.name not in [c['cate_level1'] for c in self.config.get('category_mappings')]:
            raise RuntimeError('cate_level1的值未在站点描述配置中存在：%s' % t.cate_level1)

    def test_torrent_list(self, torrent_list):
        for t in torrent_list:
            self.test_torrent(t)

    async def test_download(self, torrent):
        import tempfile
        filepath = os.path.join(tempfile.gettempdir(), "%s.torrent" % time.time())
        await self.helper.download(torrent.download_url, filepath)
        if not os.path.exists(filepath) or os.path.getsize(filepath) <= 0:
            raise RuntimeError('下载文件失败，下载链接：%s' % torrent.download_url)
        os.remove(filepath)

    async def test_search(self):
        print('开始无参数搜索测试（获取种子列表页）')
        r = await self.helper.search()
        self.check_list(r, '无参数列表页')
        self.test_torrent_list(r)
        print('无参数列表页搜索测试通过')
        print('开始常规电影搜索测试')
        r = await self.helper.search(keyword='复仇者联盟', cate_level1_list=[CateLevel1.Movie])
        self.check_list(r, '复仇者联盟')
        self.test_torrent_list(r)
        print('常规电影搜索测试通过')
        print('开始常规剧集搜索测试')
        r = await self.helper.search(keyword='绝命毒师', cate_level1_list=[CateLevel1.TV])
        self.check_list(r, '绝命毒师')
        self.test_torrent_list(r)
        print('开始测试下载种子')
        await self.test_download(r[0])
        print('常规剧集搜索测试通过')
