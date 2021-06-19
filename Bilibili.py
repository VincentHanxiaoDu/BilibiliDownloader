import hashlib
import requests
import re
import shutil
from moviepy.editor import *
import os
from tqdm import tqdm

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, " \
    "like Gecko) Chrome/76.0.3809.87 Safari/537.36"

QUALITY = {"1080p": 80, "720p": 64, "480p": 32, "360p": 16}

FILE_EXT = ".flv"


def get_play_list(url, cid, quality):
    # translated from js
    entropy = 'rbMCKn@KuamXWlPMoJGsKcbiJKUfkPF_8dABscJntvqhRSETg'
    appkey, sec = ''.join([chr(ord(i) + 2) for i in entropy[::-1]]).split(':')
    params = 'appkey=%s&cid=%s&otype=json&qn=%s&quality=%s&type=' % (
        appkey, cid, quality, quality)

    chksum = hashlib.md5(bytes(params + sec, 'utf8')).hexdigest()
    url_api = 'https://interface.bilibili.com/v2/playurl?%s&sign=%s' % (
        params, chksum)
    headers = {
        'Referer': url,
        'User-Agent': UA
    }
    html = requests.get(url_api, headers=headers).json()
    video_list = []
    for i in html['durl']:
        video_list.append(i['url'])
    return video_list


def get_aid(url):
    text = requests.get(url, headers={"User-Agent": UA}).text
    aid_search = re.search(r"av(\d+)", url)
    # bid
    if aid_search is None:
        text = requests.get(url, headers={"User-Agent": UA}).text
        aid = re.search(r"\"aid\"\:(\d+),", text).group(1)
        return aid
    # aid
    else:
        return aid_search.group(1)


def get_video_info(aid, episode=None):
    api_url = "https://api.bilibili.com/x/web-interface/view?aid={}".format(
        aid)
    # get video info json
    vid_info_json = requests.get(api_url, headers={"User-Agent": UA}).json()
    data = vid_info_json['data']
    video_title = data["title"].replace(" ", "_")
    cid_list = list()
    pages = data['pages']
    if episode is None:
        cid_list = pages
    else:
        for e in episode:
            if e <= len(pages):
                cid_list.append(pages[e - 1])
    multiple = False
    if len(cid_list) > 1:
        multiple = True
    return video_title, cid_list, multiple


def download_video(video_list, base_dir, name, video_url, buffer_size=100000):
    temp = os.path.join(base_dir, ".download")
    if os.path.exists(temp):
        shutil.rmtree(temp)
    os.mkdir(temp)
    print("downloading: " + name)
    for p, part in enumerate(video_list):
        headers = {
            'User-Agent': UA,
            'Range': 'bytes=0-',
            'Referer': video_url,
        }
        if hasattr(tqdm, '_instances'):
            tqdm._instances.clear()
        with requests.get(part, headers=headers, stream=True) as response:
            response.raise_for_status()
            total_size_in_bytes = int(
                response.headers.get('content-length', 0))
            progression_bar = tqdm(total=total_size_in_bytes, unit='iB',
                                   unit_scale=True)
            with open(os.path.join(temp, str(p) + FILE_EXT), "wb") as f:
                for chunk in response.iter_content(chunk_size=buffer_size):
                    progression_bar.update(len(chunk))
                    f.write(chunk)
                progression_bar.close()
    return len(video_list)


def concatenate_clips(base_dir, length, name):
    print("concatenating clips: " + name)
    temp = os.path.join(base_dir, ".download")
    filename = name + FILE_EXT
    if length == 1:
        shutil.move(os.path.join(temp, "0.flv"),
                    os.path.join(base_dir, filename))
    else:
        video_list = []
        [video_list.append(VideoFileClip(os.path.join(
            temp, str(p) + FILE_EXT))) for p in range(length)]
        final_clip = concatenate_videoclips(video_list)
        final_clip.to_videofile(os.path.join(
            base_dir, filename), remove_temp=True, codec="h264")
    shutil.rmtree(temp)
    return filename


def download(url, episode=None, filename=None, quality=80, base_dir=None):
    # switch url to aid
    aid = get_aid(url)
    # get video info
    video_title, cid_list, multiple = get_video_info(aid, episode)
    if filename is None:
        filename = re.sub(r'[\/\\:*?"<>|]', '', video_title)
    else:
        filename = re.sub(r'[\/\\:*?"<>|]', '', filename)
    # path
    if base_dir is None:
        base_dir = os.path.join(os.path.dirname(
            os.path.realpath(__file__)), "downloads")
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    video_downloaded = []
    for ep in cid_list:
        # file name for each episode
        name = filename
        if multiple:
            name = filename + " " + re.sub(r'[\/\\:*?"<>|]', '', ep["part"])
        video_url = "https://api.bilibili.com/x/web-interface/view?aid={}/?p={}".format(
            aid, ep['page'])
        cid = str(ep['cid'])
        video_list = get_play_list(video_url, cid, quality)
        length = download_video(video_list, base_dir, name, video_url)
        video_file_name = concatenate_clips(base_dir, length, name)
        print("downloaded: " + name)
        video_downloaded.append(video_file_name)
    return video_downloaded


if __name__ == "__main__":
    # episode indices start at 1.
    download("https://www.bilibili.com/video/BV1DE411W7kj",
             episode=[1, 3, 4], quality=QUALITY["1080p"])
