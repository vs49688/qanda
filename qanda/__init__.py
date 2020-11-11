#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import sys
import bs4
import collections
import urllib.parse
import urllib.request
import datetime
import json
import html

EpisodeInfo = collections.namedtuple('EpisodeInfo', [
    'episode_id', 'title', 'link', 'image_url', 'teaser', 'time', 'download_url', 'size'
])


# Rip the episode info from a page. Returns the number of results added.
def parse_year_page(xx: bs4.BeautifulSoup, episodes: dict):
    before = len(episodes)

    for li in xx.find_all('li', recursive=True):

        img = li.find('div', class_='image')
        if img:
            image_url = img.find('img').attrs['src']
        else:
            image_url = None

        description = li.find('div', class_='description')
        titlea = description.find('h3').find('a')

        path = titlea.attrs['href']

        episode = EpisodeInfo(
            episode_id=int(path.split('/', 3)[-1]),
            title=titlea.text.strip(),
            link=urllib.parse.urlunparse((
                'https',
                'www.abc.net.au',
                path,
                '',
                '',
                ''
            )),
            image_url=image_url,
            teaser=' '.join(i.strip() for i in description.find('div', class_='teaser-text').text.split('\n')).strip(),
            time=description.find('time').attrs['datetime'],
            download_url=None,
            size=None
        )

        episodes[episode.episode_id] = episode

    return len(episodes) - before


# Fetch all episodes in a year
def fetch_year(year: int, episodes: dict):

    params = {
        'view': 'findarchive.ajax',
        'year': str(year),
    }

    pg = 1
    while True:
        params['pageNum'] = str(pg)

        url = urllib.parse.urlunparse((
            'https',
            'www.abc.net.au',
            '/qanda/episodes/pagination/search/archive/10466362',
            '',
            urllib.parse.urlencode(params),
            ''
        ))

        req = urllib.request.Request(
            url=url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )

        with urllib.request.urlopen(req) as x:
            if x.getcode() != 200:
                raise Exception(f'HTTP {x.getcode()} on {url}')
            html = bs4.BeautifulSoup(x.read().decode('utf-8'), 'html5lib')

        amount = parse_year_page(html, episodes)
        #print(f'Added {amount} episodes...', file=sys.stderr)
        if amount == 0:
            break
        pg += 1


def _get_image_url(html: bs4.BeautifulSoup, ep: EpisodeInfo) -> str:
    meta = html.find('meta', property='og:image')
    if not meta:
        meta = html.find('meta', property='twitter:image')
    if not meta:
        return ep.image_url

    return meta.get('content', ep.image_url)


def _get_title(html: bs4.BeautifulSoup, ep: EpisodeInfo) -> str:
    meta = html.find('meta', property='title')
    if not meta:
        meta = html.find('meta', property='og:title')
    if not meta:
        meta = html.find('meta', property='DCTERMS.title')

    if meta.has_attr('title'):
        return meta.get('content')

    h1 = html.find('h1', itemprop='name')
    if h1:
        return h1.text

    return ep.title


def _get_description(html: bs4.BeautifulSoup, ep: EpisodeInfo) -> str:
    meta = html.find('meta', property='description')
    if not meta:
        meta = html.find('meta', property='og:description')

    return meta.get('content', ep.teaser)


def _get_download_url(html: bs4.BeautifulSoup):
    span = html.find('span', class_='download')
    if not span:
        return None

    a = span.find('a')
    if not a:
        return None

    return a.get('href')


def fetch_pageinfo(ep: EpisodeInfo) -> EpisodeInfo:
    req = urllib.request.Request(
        url=ep.link,
        headers={'User-Agent': 'Mozilla/5.0'}
    )

    with urllib.request.urlopen(req) as x:
        if x.getcode() != 200:
            raise Exception(f'HTTP {x.getcode()} on {ep.link}')
        html = bs4.BeautifulSoup(x.read().decode('utf-8'), 'html5lib')

    ##
    # Read the metadata, it tends to be higher quality than what
    # was scraped previously.
    ##
    return ep._replace(
        title=_get_title(html, ep),
        teaser=_get_description(html, ep),
        image_url=_get_image_url(html, ep),
        download_url=_get_download_url(html)
    )


"""
HEAD'ing https://abcmedia.akamaized.net/tv/qanda/vodcast/qanda_2011_ep39.mp4
Server: Apache
Last-Modified: Mon, 07 Nov 2011 12:09:24 GMT
ETag: "cc0497d-4b123ecfec60f"
Accept-Ranges: bytes
Content-Length: 213928317
Content-Disposition: attachment
Content-Type: application/octet-stream
Date: Wed, 11 Nov 2020 01:12:40 GMT
Connection: close
X-Forward-Proto: http
CDN-Origin-Protocol: HTTP
"""


def get_size(ep: EpisodeInfo) -> EpisodeInfo:
    if not ep.download_url:
        return ep._replace(size=0)

    req = urllib.request.Request(
        url=ep.download_url,
        headers={'User-Agent': 'Mozilla/5.0'},
        method='HEAD'
    )

    with urllib.request.urlopen(req) as x:
        if x.getcode() != 200:
            raise Exception(f'HTTP {x.getcode()} on {ep.download_url}')

        return ep._replace(size=int(x.headers['Content-Length']))


def parse_timestamp(ts: str) -> datetime.datetime:
    return datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M%z')


def from_json(fp):
    data = json.load(fp)
    return {int(id): EpisodeInfo(**data[id]) for id in data}


def to_json(episodes: dict, fp):
    json.dump({e: episodes[e]._asdict() for e in episodes}, fp, indent=4)


def build_podcast(episodes) -> bytes:
    import feedgen.feed
    episodes = sorted(episodes, key=lambda x: parse_timestamp(x.time))

    fg = feedgen.feed.FeedGenerator()
    fg.load_extension('podcast')

    fg.title('Q+A')
    fg.description('Q+A is a television discussion program that focuses mostly on politics but ranges across all of '
                   'the big issues that set Australians thinking, talking and debating.')
    fg.link(href='https://www.abc.net.au/qanda')
    fg.language('en')
    fg.webMaster('webmaster@vs49688.net')
    fg.podcast.itunes_explicit = True

    for ep in episodes:
        time = parse_timestamp(ep.time)
        fe = fg.add_entry()
        fe.guid(guid=ep.link, permalink=True)
        fe.title(ep.title)
        fe.description(html.escape(ep.teaser), True)
        fe.pubDate(time)
        fe.link(href=ep.link)

        if ep.download_url:
            fe.enclosure(url=ep.download_url, length=str(ep.size), type='video/mp4')

    return fg.rss_str(pretty=True)
