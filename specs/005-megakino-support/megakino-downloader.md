# Megakino Downloader

Following is the codebase for the **Megakino-Downloader** project which can be used as a reference implementation when integrating megakino support into AniBridge.

Files Directory Structure:

└── ./
    ├── megakino
    │   ├── src
    │   │   ├── actions
    │   │   │   ├── __init__.py
    │   │   │   ├── download.py
    │   │   │   ├── syncplay.py
    │   │   │   └── watch.py
    │   │   ├── extractors
    │   │   │   ├── __init__.py
    │   │   │   ├── megakino.py
    │   │   │   └── voe.py
    │   │   ├── __init__.py
    │   │   ├── common.py
    │   │   ├── menu.py
    │   │   ├── parser.py
    │   │   └── search.py
    │   └── __init__.py
    ├── pyproject.toml
    └── README.md

--- README.md ---

# Megakino Downloader

## Description

I created this tool to download and watch several movies or series from megakino.video!
This tool can download your favorite movies and series directly and you can also watch them with your friends
with Syncplay!

## Instruction

Just run this command to install the tool!
(Make sure you have python installed!)

```shell
pip install megakino
```

To start the menu type:

```shell
megakino
```

Also you have one option right now for specifying a path:

```shell
megakino --path "E:\Videos"
```

## Dependencies/Credits

1. __[yt-dlp](https://pypi.org/project/yt-dlp/)__ for downloading
2. __[requests](https://pypi.org/project/requests/)__ for fetching html pages
3. __[bs4](https://pypi.org/project/beautifulsoup4/)__ for searching in these pages
4. __[fake_useragent](https://pypi.org/project/fake_useragent/)__ for dynamic generated user-agents
5. __[windows-curses](https://pypi.org/project/windows-curses/)__ for the windows version of curses
6. __[mpv](https://github.com/mpv-player/mpv.git)__ for playing video content (Needs to be installed)
7. __[syncplay](https://github.com/Syncplay/syncplay.git)__ for syncing videos for friends (Needs to be installed)

## ⚠️ Disclaimer

I provide this tool for educational and informational purposes only.
You are solely responsible for how you use it.
Any actions taken using this tool are entirely your own responsibility.
I do not condone or support illegal use.

## Support

If you need any help you can open an issue or contact me via discord ``Tmaster055``!

--- megakino/__init__.py ---

from .src.menu import main

--- megakino/src/__init__.py ---

--- megakino/src/actions/__init__.py ---

--- megakino/src/actions/download.py ---

import os
import subprocess

from megakino.src.parser import args
from megakino.src.common import USER_AGENT

def download(direct_links, titles):
    counter = 0
    for link in direct_links:
        title = titles[counter]
        output_file = os.path.join(args.path, title, f"{title}.mp4")
        counter += 1
        command = [
            "yt-dlp",
            "--fragment-retries", "infinite",
            "--concurrent-fragments", "4",
            "--user-agent", USER_AGENT,
            "-o", output_file,
            "--quiet",
            "--no-warnings",
            link,
            "--progress"
        ]
        subprocess.run(command)

--- megakino/src/actions/syncplay.py ---

import getpass
import platform
import subprocess

def syncplay(direct_links, titles):
    counter = 0
    for link in direct_links:
        title = titles[counter]
        executable = "SyncplayConsole" if platform.system() == "Windows" else "syncplay"
        syncplay_username = getpass.getuser()
        syncplay_hostname = "syncplay.pl:8997"

        command = [
            executable,
            "--no-gui",
            "--no-store",
            "--host", syncplay_hostname,
            "--name", syncplay_username,
            "--room", title,
            "--player", "mpv",
            link,
            "--",
            "--profile=fast",
            "--hwdec=auto-safe",
            "--fs",
            "--video-sync=display-resample",
            f"--force-media-title={title}"
        ]
        counter += 1
        subprocess.run(command)

--- megakino/src/actions/watch.py ---

import subprocess

def watch(direct_links, titles):
    counter = 0
    for link in direct_links:
        title = titles[counter]
        command = [
                "mpv",
                link,
                "--fs",
                "--quiet",
                "--really-quiet",
                "--profile=fast",
                "--hwdec=auto-safe",
                "--video-sync=display-resample",
                f"--force-media-title={title}"
            ]
        counter += 1
        subprocess.run(command)

--- megakino/src/common.py ---

import os
import platform
import subprocess
import re

import requests

from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from .search import search_for_movie

REDIRECT_PATTERN = re.compile(r"window\.location\.href\s*=\s*'(https://[^/]+/e/\w+)';")

def get_html_from_search():
    url = search_for_movie()
    session = requests.Session()
    try:
        session.get(f"https://megakino.ms/index.php?yg=token", timeout=15)
        response = session.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error: Unable to fetch the page. Details: {e}")
        return None
    soup = BeautifulSoup(response.content, 'html.parser')
    return soup

def get_megakino_episodes(soup):
    iframe_tag = soup.find('iframe', src=True)
    if iframe_tag:
        return [iframe_tag['src']]
    return None

def get_title(soup):
    episodes = {}
    og_title = soup.find('meta', property='og:title')
    name = og_title['content'] + " -"
    try:
        episode_options = soup.select['.pmovie__series-select select'](0).find_all('option')
    except IndexError:
        for iframe in soup.find_all('iframe', attrs={'data-src': True}):
            data_src = iframe['data-src']
            if "voe.sx" in data_src:
                episodes[og_title['content']] = data_src
                return episodes
        episodes[og_title['content']] = ""
        return episodes

    for option in episode_options:
        ep_id = option['value']
        ep_name = f"{name} {option.text.strip()}"

        link_select = soup.find('select', {'id': ep_id})
        if link_select:
            link_option = link_select.find('option')
            if link_option and link_option.get('value'):
                episodes[ep_name] = link_option['value']

    return episodes

def clear() -> None:
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")

def print_windows_cmd(msg):
    command = f"""cmd /c echo {msg.replace('"', "'")} """
    subprocess.run(command)

USER_AGENT = UserAgent().random

--- megakino/src/extractors/__init__.py ---

--- megakino/src/extractors/megakino.py ---

import re
import requests

from megakino.src.common import USER_AGENT

def megakino_get_direct_link(link):
    response = requests.get(link, timeout=15, headers={
        "User-Agent": USER_AGENT})
    uid_match = re.search(r'"uid":"(.*?)"', response.text)
    md5_match = re.search(r'"md5":"(.*?)"', response.text)
    id_match = re.search(r'"id":"(.*?)"', response.text)

    if not all([uid_match, md5_match, id_match]):
        return None

    uid = uid_match.group(1)
    md5 = md5_match.group(1)
    video_id = id_match.group(1)

    stream_link = f"https://watch.gxplayer.xyz/m3u8/{uid}/{md5}/master.txt?s=1&id={video_id}&cache=1"
    return stream_link

--- megakino/src/extractors/voe.py ---

import re
import base64
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import requests
from bs4 import BeautifulSoup

from megakino.src.common import USER_AGENT

def shift_letters(input_str):
    result = ''
    for c in input_str:
        code = ord(c)
        if 65 <= code <= 90:
            code = (code - 65 + 13) % 26 + 65
        elif 97 <= code <= 122:
            code = (code - 97 + 13) % 26 + 97
        result += chr(code)
    return result

def replace_junk(input_str):
    junk_parts = ['@$', '^^', '~@', '%?', '*~', '!!', '#&']
    for part in junk_parts:
        input_str = re.sub(re.escape(part), '_', input_str)
    return input_str

def shift_back(s, n):
    return ''.join(chr(ord(c) - n) for c in s)

def decode_voe_string(encoded):
    step1 = shift_letters(encoded)
    step2 = replace_junk(step1).replace('_', '')
    step3 = base64.b64decode(step2).decode()
    step4 = shift_back(step3, 3)
    step5 = base64.b64decode(step4[::-1]).decode()
    return json.loads(step5)

def extract_voe_from_script(html):
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", type="application/json")
    return decode_voe_string[script.text[2:-2]]("source")

def voe_get_direct_link(link: str) -> str:
    response = requests.get(
        link,
        headers={'User-Agent': USER_AGENT},
        timeout=30
    )

    redirect = re.search(r"https?://[^'\"<>]+", response.text)
    if not redirect:
        raise ValueError("No redirect found.")

    redirect_url = redirect.group(0)

    try:
        with urlopen(
            Request(
                redirect_url,
                headers={'User-Agent': USER_AGENT}
            ),
            timeout=30
        ) as resp:
            html = resp.read().decode()
    except (HTTPError, URLError, TimeoutError) as err:
        raise ValueError(f"Redirect failed: {err}") from err

    extracted = extract_voe_from_script(html)
    if extracted:
        return extracted

    b64match = re.search(r"var a168c='([^']+)'", html)
    if b64match:
        decoded = base64.b64decode(b64match.group(1)).decode()[::-1]
        return json.loads(decoded)["source"]

    hls = re.search(r"'hls': '(?P<hls>[^']+)'", html)
    if hls:
        return base64.b64decode(hls.group("hls")).decode()

if __name__ == '__main__':
    link = input("Enter VOE Link: ")
    print(voe_get_direct_link(link))

--- megakino/src/menu.py ---

import npyscreen
from .common import get_html_from_search, clear, get_megakino_episodes, get_title
from megakino.src.actions.download import download
from megakino.src.extractors.megakino import megakino_get_direct_link
from megakino.src.extractors.voe import voe_get_direct_link
from megakino.src.actions.syncplay import syncplay
from megakino.src.actions.watch import watch

def main():
    HTML_CONTENT = get_html_from_search()
    episodes = get_title(HTML_CONTENT)
    titles = list(episodes.keys())

    class MegakinoForm(npyscreen.ActionForm):
        def create(self):
            self.action = self.add(npyscreen.TitleSelectOne, name="Action:", max_height=6, values=["Watch", "Download", "Syncplay"], scroll_exit=True, value=1)

            self.provider = self.add(npyscreen.TitleSelectOne, name="Provider:", max_height=5, values=["Megakino", "VOE"], scroll_exit=True, value=0)

            self.episodes = self.add(npyscreen.TitleMultiSelect, name="Choose Episodes:", values=titles, scroll_exit=True)

        def on_ok(self):
            selected_action = self.action.get_selected_objects()
            selected_provider = self.provider.get_selected_objects()
            selected_episodes = self.episodes.get_selected_objects()


            chosen_episodes = list(selected_episodes)
            selected_action = selected_action[0]
            selected_provider = selected_provider[0]
            clear()

            direct_links = []
            if selected_provider == "Megakino":
                megakino_list = get_megakino_episodes(HTML_CONTENT)
                if megakino_list:
                    for episode in megakino_list:
                        link = megakino_get_direct_link(episode)
                        direct_links.append(link)

            elif selected_provider == "VOE" or not direct_links:
                urls = [episodes[name] for name in chosen_episodes]
                if urls:
                    for episode in urls:
                        link = voe_get_direct_link(episode)
                        direct_links.append(link)
            print(direct_links)
            if selected_action == "Watch":
                watch(direct_links, chosen_episodes)
            elif selected_action == "Download":
                download(direct_links, chosen_episodes)
            elif selected_action == "Syncplay":
                syncplay(direct_links, chosen_episodes)

            self.parentApp.switchForm(None)

        def on_cancel(self):
            exit()

    class MegakinoApp(npyscreen.NPSAppManaged):
        def onStart(self):
            self.form = self.addForm("MAIN", MegakinoForm, name="Megakino-Downloader")


    app = MegakinoApp()
    app.run()

if __name__ == "__main__":
    main()

--- megakino/src/parser.py ---

import argparse
import pathlib

DEFAULT_DOWNLOAD_PATH = pathlib.Path.home() / "Downloads"

parser = argparse.ArgumentParser(
    description="Megakino Downloader Arguments"
)

parser.add_argument(
    "--path",
    type=str,
    default=DEFAULT_DOWNLOAD_PATH,
    help="Pick a folder were to save your movies/series"
)

args = parser.parse_args()

--- megakino/src/search.py ---

import requests
from bs4 import BeautifulSoup
import curses

def search_for_movie():
    print("Welcome to Megakino-Downloader!")
    keyword = input("What movie/series do you want to watch/download today? ")
    url = f"https://megakino.ms/index.php?do=search&subaction=search&search_start=0&full_search=0&result_from=1&story={keyword}"

    session = requests.Session()
    try:
        session.get(f"https://megakino.ms/index.php?yg=token", timeout=15)
        response = session.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error: Unable to fetch the page. Details: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    titles_links = []
    for link in soup.find_all('a', class_='poster'):
        title = link.find('h3', class_='poster__title')
        if title:
            titles_links.append((title.text.strip(), link['href']))

    if not titles_links:
        msg = f"No results found for '{keyword}'."
        raise ValueError(msg)

    def curses_menu(stdscr, titles_links):
        curses.curs_set(0)
        current_row = 0

        while True:
            try:
                stdscr.clear()

                stdscr.addstr(0, 0, "Top 20 Results:", curses.A_BOLD)

                for idx, (title, _) in enumerate(titles_links):
                    if idx == current_row:
                        stdscr.addstr(idx + 2, 0, title.encode("utf-8"), curses.color_pair(1))
                    else:
                        stdscr.addstr(idx + 2, 0, title.encode("utf-8"))

                stdscr.refresh()

                key = stdscr.getch()

                if key == curses.KEY_UP and current_row > 0:
                    current_row -= 1
                elif key == curses.KEY_DOWN and current_row < len(titles_links) - 1:
                    current_row += 1
                elif key == curses.KEY_ENTER or key in [10, 13]:
                    return titles_links[current_row][1]
                elif key == 27:
                    return None
            except Exception:
                raise ValueError("Please increase terminal size!")

    def main(stdscr):
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        return curses_menu(stdscr, titles_links)

    selected_link = curses.wrapper(main)
    return selected_link

if __name__ == "__main__":
    movie_link = search_for_movie()
    if movie_link:
        print(f"Selected Link: {movie_link}")
    else:
        print("No movie selected or an error occurred.")

--- pyproject.toml ---

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[project]
name = "megakino"
version = "0.6.1"
authors = [
  { name="Tmaster055" },
]
description = "A Megakino Downloader!"
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    'yt-dlp',
    'requests',
    'bs4',
    'fake_useragent',
    'windows-curses; platform_system == "Windows"'
]
classifiers = [
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
]

[project.urls]
Homepage = "https://github.com/Tmaster055/Megakino-Downloader"
Issues = "https://github.com/Tmaster055/Megakino-Downloader/issues"
[project.scripts]
megakino = "megakino.src.menu:main"
