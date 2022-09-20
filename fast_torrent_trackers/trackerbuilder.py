from fast_torrent_trackers.basetracker import BaseTracker
from fast_torrent_trackers.tracker.rarbg import Rarbg
from fast_torrent_trackers.tracker.spidertracker import SpiderTracker


class TrackerBuilder:
    @staticmethod
    def build(site_config, cookie=None, proxies=None, user_agent=None) -> BaseTracker:
        if not site_config:
            return
        if site_config.get('parser'):
            parser = site_config.get('parser')
        else:
            parser = 'SpiderTracker'
        if parser == 'NexusPHP' or parser == 'SpiderTracker':
            return SpiderTracker(site_config, cookie, proxies=proxies, user_agent=user_agent)
        elif parser == 'RARBG':
            return Rarbg(site_config, proxies=proxies)
