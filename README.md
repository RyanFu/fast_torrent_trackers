种子搜索下载工具
==============
种子资源搜索、下载API，支持BT/PT站点(API Support for your favorite torrent trackers)

## 安装

使用pip安装:

```
pip install fast-torrent-trackers
```

## 快速开始

```
with open('tracker解析描述文件地址.yml', 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)
tracker = TrackerBuilder.build(config,
                               'your cookies')
print(asyncio.run(tracker.get_userinfo()).__dict__)
```