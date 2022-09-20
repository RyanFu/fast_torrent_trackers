# -*- coding: utf-8 -*-
from setuptools import setup

# Get README.rst contents
with open('README.md', 'r', encoding="utf-8") as f:
    readme = f.read()
requirements = []
with open('requirements.txt') as handle:
    for line in handle.readlines():
        if not line.startswith('#'):
            package = line.strip().split('=', 1)[0]
            requirements.append(package)
setup(
    name='fast-torrent-trackers',
    version='0.0.1',
    author='yee',
    author_email='yipengfei329@gmail.com',
    url='https://github.com/pofey/fast_torrent_trackers',
    description='快速开始搜索种子、下载种子(API Support for your favorite torrent trackers)',
    python_requires='>=3.8',
    long_description=readme,
    long_description_content_type="text/markdown",
    keywords=['torrent', 'tracker', 'bt', 'pt'],
    packages=['fast_torrent_trackers'],
    install_requires=requirements
)
