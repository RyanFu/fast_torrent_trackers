from abc import ABCMeta, abstractmethod
from typing import List

from random_user_agent.params import SoftwareName
from random_user_agent.user_agent import UserAgent

from fast_torrent_trackers.models import CateLevel1, TrackerUserinfo, TorrentList
from fast_torrent_trackers.utils import render_text

user_agent_rotator = UserAgent(
    software_names=[SoftwareName.CHROME.value, SoftwareName.FIREFOX.value, SoftwareName.ANDROID.value,
                    SoftwareName.OPERA.value, SoftwareName.OPERA_MINI.value, SoftwareName.UC_BROWSER.value,
                    SoftwareName.SAFARI.value],
    limit=100)


class BaseTracker(metaclass=ABCMeta):
    category_mappings = None
    site_config = None
    cookies = None

    def get_id(self):
        return self.site_config.get('id')

    def get_name(self):
        return self.site_config.get('name')

    def get_domain(self):
        return self.site_config.get('domain')

    def get_encoding(self):
        return self.site_config.get('encoding')

    def get_sub_search_value_type(self):
        return self.site_config.get('sub_search_value_type', ['cn_name', 'en_name'])

    def get_download_method(self):
        return str(self.site_config.get('download', {'method': 'GET'}).get('method', 'GET')).upper()

    def get_download_content_type(self):
        return self.site_config.get('download', {'method': 'GET'}).get('content_type')

    def get_download_args(self):
        args = self.site_config.get('download', {'method': 'GET'}).get('args', None)
        if not args:
            return args
        payload: dict = dict()
        for p in args:
            if isinstance(p.get('value'), str) and str(p.get('value')).startswith('{'):
                payload[p.get('name')] = render_text(p.get('value'))
            else:
                payload[p.get('name')] = p.get('value')
        return payload

    def _get_response_text(self, r):
        return str(r.content, self.get_encoding())

    @staticmethod
    def _init_category_mappings(category_mappings):
        cates = []
        for c in category_mappings:
            c['id'] = str(c['id'])
            cates.append(c)
        return category_mappings

    def _get_cate_id_from_level2(self, level2):
        if not level2:
            return
        for c in self.category_mappings:
            if c.get('cate_level2') == level2:
                return c.get('id')
        return

    def _get_cate_level2_ids(self, cate_level1_list: List[CateLevel1] = None):
        """
        通过一级大分类，去找到配置好的站点二级小分类，真正搜索时，搜站点二级小分类的编号
        :param cate_level1_list:
        :return:
        """
        if not cate_level1_list:
            ids = []
            # 为空不查成人
            for c in self.category_mappings:
                if c['cate_level1'] == CateLevel1.AV.name:
                    continue
                ids.append(c['id'])
            return ids
        cate_level1_str_arr = [i.name for i in cate_level1_list]
        cate2_ids = []
        # 找到一级分类下所有的二级分类编号
        for c in self.category_mappings:
            if c.get('cate_level1') in cate_level1_str_arr or c.get('cate_level1') == '*':
                cate2_ids.append(c.get('id'))
        return cate2_ids

    def _trans_search_cate_id(self, ids):
        if not ids:
            return ids
        id_mapping = self.site_config.get('category_id_mapping')
        if not id_mapping:
            return ids
        new_ids = []
        for id in ids:
            for mid in id_mapping:
                if mid.get('id') == id:
                    if isinstance(mid.get('mapping'), list):
                        new_ids += mid.get('mapping')
                    else:
                        new_ids.append(mid.get('mapping'))
        return list(filter(None, new_ids))

    @abstractmethod
    async def get_userinfo(self, refresh=False) -> TrackerUserinfo:
        pass

    @abstractmethod
    async def search(self, keyword=None, imdb_id=None, cate_level1_list: list = None, free: bool = False,
                     page: int = None,
                     timeout=None) -> TorrentList:
        pass

    @abstractmethod
    async def download(self, url, filepath):
        pass
