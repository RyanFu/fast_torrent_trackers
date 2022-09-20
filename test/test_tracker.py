import asyncio
import os
import unittest

import yaml

from fast_torrent_trackers.trackerbuilder import TrackerBuilder


class TestTracker(unittest.TestCase):
    def test_build(self):
        with open(os.path.join(os.path.abspath('..'), 'trackers_config', 'mteam.yml'), 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        tracker = TrackerBuilder.build(config,
                                       'your cookies')
        print(asyncio.run(tracker.get_userinfo()).__dict__)
