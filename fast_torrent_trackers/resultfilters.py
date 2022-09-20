import datetime
import json
import re

from fast_torrent_trackers.models import TorrentList


async def hdchina_free_ajax_filter(client, search_html_text, torrents: TorrentList):
    mcsrf = re.search(r'<meta name="x-csrf" content="([^"]+)"/>', search_html_text)
    if mcsrf:
        csrf = mcsrf.group(1)
    else:
        csrf = ''
    post_str = ''
    for t in torrents:
        post_str += f'ids%5B%5D={t.id}&'
    post_str += 'csrf=' + csrf
    free_res = await client.post(
        url='https://hdchina.org/ajax_promotion.php',
        data=post_str,
        headers={
            'referer': 'https://hdchina.org/torrents.php',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8'
        },
        cookies=client.cookies
    )
    free_info_json = json.loads(free_res.text)
    for t in torrents:
        if str(t.id) not in free_info_json['message']:
            continue
        free_info = free_info_json['message'][str(t.id)]
        sp_state = free_info['sp_state']
        if sp_state.find('pro_free') != -1:
            t.download_volume_factor = 0.0
        elif sp_state.find('pro_free2up') != -1:
            t.download_volume_factor = 0.0
            t.upload_volume_factor = 2
        elif sp_state.find('pro_50pctdown') != -1:
            t.download_volume_factor = 0.5
        elif sp_state.find('pro_50pctdown2up') != -1:
            t.download_volume_factor = 0.5
            t.upload_volume_factor = 2
        elif sp_state.find('pro_30pctdown') != -1:
            t.download_volume_factor = 0.3
        elif sp_state.find('pro_2up') != -1:
            t.upload_volume_factor = 2
        else:
            t.download_volume_factor = 1.0
        if t.download_volume_factor == 0.0:
            if free_info['timeout'] == '':
                # 默认为不免费，避免损失
                t.download_volume_factor = 1.0
            else:
                mtime = re.search(r'\d+-\d+-\d+ \d+:\d+:\d+', free_info['timeout'])
                if mtime:
                    t.free_deadline = datetime.datetime.strptime(mtime.group(), '%Y-%m-%d %H:%M:%S')
    return free_res


result_filters = {
    'hdchina_free_ajax_filter': hdchina_free_ajax_filter
}
