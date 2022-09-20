import datetime
from enum import Enum
from typing import List

from fast_torrent_trackers.utils import DictWrapper, trans_size_str_to_mb


class CateLevel1(str, Enum):
    Movie = '电影'
    TV = '剧集'
    Documentary = '纪录片'
    Anime = '动漫'
    Music = '音乐'
    Game = '游戏'
    AV = '成人'
    Other = '其他'

    @staticmethod
    def get_type(enum_name: str):
        for item in CateLevel1:
            if item.name == enum_name:
                return item
        return None


class TrackerUserinfo:
    uid: int
    username: str
    user_group: str
    share_ratio: float
    uploaded: float
    downloaded: float
    seeding: int
    leeching: int
    vip_group: bool = False


class TorrentInfo:
    # 站点编号
    site_id: str
    # 种子编号
    id: int
    # 种子名称
    name: str
    # 种子标题
    subject: str
    # 以及类目
    cate_level1: CateLevel1 = None
    # 站点类目id
    cate_id: str
    # 种子详情页地址
    details_url: str
    # 种子下载链接
    download_url: str
    # 种子关联的imdbid
    imdb_id: str
    # 种子发布时间
    publish_date: datetime
    # 种子大小，转化为mb尺寸
    size_mb: float
    # 做种人数
    upload_count: int
    # 下载中人数
    downloading_count: int
    # 下载完成人数
    download_count: int
    # 免费截止时间
    free_deadline: datetime
    # 下载折扣，1为不免费
    download_volume_factor: float
    # 做种上传系数，1为正常
    upload_volume_factor: int
    minimum_ratio: float = 0
    minimum_seed_time: int = 0
    # 封面链接
    poster_url: str

    @staticmethod
    def build_by_parse_item(site_config, item):
        item = DictWrapper(item or {})
        t = TorrentInfo()
        t.site_id = site_config.get('id')
        t.id = item.get_int('id', 0)
        t.name = item.get_value('title', '')
        t.subject = item.get_value('description', '')
        if t.subject:
            t.subject = t.subject.strip()
        t.free_deadline = item.get('free_deadline')
        t.imdb_id = item.get('imdbid')
        t.upload_count = item.get_int('seeders', 0)
        t.downloading_count = item.get_int('leechers', 0)
        t.download_count = item.get_int('grabs', 0)
        t.download_url = item.get('download')
        if t.download_url and not t.download_url.startswith('http'):
            t.download_url = site_config.get('domain') + t.download_url
        t.publish_date = item.get_value('date', datetime.datetime.now())
        t.cate_id = str(item.get('category')) if item.get('category') else None
        for c in site_config.get('category_mappings'):
            if c.get('id') == t.cate_id:
                t.cate_level1 = CateLevel1.get_type(c.get('cate_level1'))
        t.details_url = item.get('details')
        if t.details_url:
            t.details_url = site_config.get('domain') + t.details_url
        t.download_volume_factor = float(item.get_value('downloadvolumefactor', 1))
        t.upload_volume_factor = item.get_value('uploadvolumefactor', 1)
        t.size_mb = trans_size_str_to_mb(str(item.get_value('size', 0)))
        t.poster_url = item.get('poster')
        t.minimum_ratio = item.get_float('minimumratio', 0.0)
        t.minimum_seed_time = item.get_int('minimumseedtime', 0)
        if t.poster_url:
            if t.poster_url.startswith("./"):
                t.poster_url = site_config.get('domain') + t.poster_url[2:]
            elif not t.poster_url.startswith("http"):
                t.poster_url = site_config.get('domain') + t.poster_url
        return t


TorrentList = List[TorrentInfo]
