import asyncio
import logging
import time

from tenacity import stop_after_delay, wait_exponential, retry_if_not_exception_type, AsyncRetrying

from fast_torrent_trackers.exceptions import LoginRequired, RequestOverloadException
from fast_torrent_trackers.models import CateLevel1

_LOGGER = logging.getLogger(__name__)


class TrackerSearcher:
    run_time = None
    interval_secs = 10

    def __init__(self, tracker, query=None, cate_level1_list: list = None, network_error_retry=False,
                 timeout: int = None, search_value_type=None):
        self.tracker = tracker
        self.query = []
        if query:
            for q in query:
                if search_value_type and q.get('value_type') and q.get('value_type') not in search_value_type:
                    continue
                self.query.append(q)
        self.network_error_retry = network_error_retry
        self.cate_level1_list = cate_level1_list
        self.timeout = timeout

    def get_run_time(self):
        return self.run_time

    def get_site_helper(self):
        return self.tracker

    def get_site_id(self):
        return self.tracker.get_id()

    def get_site_name(self):
        return self.tracker.get_name()

    def get_query_str(self):
        return [i.get('value') for i in self.query]

    async def search(self):
        start = time.perf_counter()
        try:
            ids: set = set()
            res = []
            for i, q in enumerate(self.query):
                params = {
                    q.get('key'): q.get('value'),
                    'cate_level1_list': self.cate_level1_list,
                    'timeout': self.timeout
                }
                if self.network_error_retry:
                    async for attempt in AsyncRetrying(retry=retry_if_not_exception_type(LoginRequired),
                                                       stop=stop_after_delay(600),
                                                       wait=wait_exponential(multiplier=1, min=5, max=120)):
                        with attempt:
                            try:
                                r = await self.tracker.search(**params)
                            except RequestOverloadException as e:
                                await asyncio.sleep(e.stop_secs)
                                raise e
                            except Exception as e:
                                _LOGGER.info(f"{self.get_site_name()}搜索{q.get('value')}出错，自动重试中，错误信息：{e}")
                                raise e
                else:
                    r = await self.tracker.search(**params)
                if not r:
                    continue
                for t in r:
                    if t.id in ids:
                        continue
                    res.append(t)
                    ids.add(t.id)
                if i + 1 < len(self.query):
                    await asyncio.sleep(self.interval_secs)
            return {'code': 0, 'data': res}
        except LoginRequired as e:
            raise e
        except Exception as e:
            _LOGGER.error('从%s搜索 %s 失败了，错误信息: %s' % (self.tracker.get_name(), self.get_query_str(), e),
                          exc_info=True)
            return {'code': 1, 'data': []}
        finally:
            end = time.perf_counter()
            self.run_time = end - start

    async def list(self):
        start = time.perf_counter()
        try:
            params = {'cate_level1_list': [CateLevel1.Movie,
                                           CateLevel1.TV,
                                           CateLevel1.Documentary,
                                           CateLevel1.Anime,
                                           CateLevel1.Music,
                                           CateLevel1.AV,
                                           CateLevel1.Game,
                                           CateLevel1.Other], 'timeout': 10}
            if self.network_error_retry:
                async for attempt in AsyncRetrying(retry=retry_if_not_exception_type(LoginRequired),
                                                   stop=stop_after_delay(600),
                                                   wait=wait_exponential(multiplier=1, min=20, max=120)):
                    with attempt:
                        try:
                            r = await self.tracker.search(**params)
                        except RequestOverloadException as e:
                            await asyncio.sleep(e.stop_secs)
                            raise e
                        except Exception as e:
                            _LOGGER.info(f"{self.get_site_name()}获取最新种子列表出错，自动重试中，错误信息：{e}")
                            raise e
            else:
                r = await self.tracker.search(**params)
            return r
        except LoginRequired as e:
            raise e
        except Exception as e:
            return
        finally:
            end = time.perf_counter()
            self.run_time = end - start
