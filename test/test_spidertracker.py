import asyncio
import os
import unittest

from fast_torrent_trackers.trackertester import TrackerTester


class TestSpiderTracker(unittest.TestCase):
    def test_mteam(self):
        test = TrackerTester(os.path.join(os.path.abspath('..'), 'trackers_config', 'mteam.yml'),
                             'your cookies')
        asyncio.run(test.start_test())
