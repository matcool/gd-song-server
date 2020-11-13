from aiohttp import web, ClientSession
from urllib.parse import unquote, quote
import asyncio
import json
import re
from bs4 import BeautifulSoup
import sys

# Change this if you don't want caching, for whatever reason
CACHE = True

if CACHE:
    import sqlite3

    class DBConnect:
        def __init__(self, path: str):
            self.path = path
            self.conn = sqlite3.connect(self.path)

        def close(self):
            self.conn.close()

        def __enter__(self):
            return self.conn.cursor()
        
        def __exit__(self, *args):
            self.conn.commit()

    db = DBConnect('song_cache.db')
    with db as c:
        c.execute('CREATE TABLE IF NOT EXISTS songs (id integer, name text, artist text, size int, url text)')


async def get_song_official(song_id: int):
    async with ClientSession() as session:
        async with session.post(f'http://www.boomlings.com/database/getGJSongInfo.php', data={'songID': song_id, 'secret': 'Wmfd2893gb7'}) as resp:
            return await resp.text()

async def scrape_song_ng(song_id: int):
    async with ClientSession() as session:
        async with session.get(f'https://www.newgrounds.com/audio/listen/{song_id}') as resp:
            raw_page = await resp.text()
        
    soup = BeautifulSoup(raw_page, 'html.parser')

    script_tag = soup.find('script', text=re.compile('new embedController'))
    if script_tag is None:
        return
    obj = re.search(r'new embedController\(\[({.+})\],', script_tag.string, flags=re.S).group(1)
    # remove some js code
    obj = re.sub(r',\s*callback\s*:\s*function\s*\(\)\s*{\s*[\s\S]+\s*}\s*\)\s*\(jQuery\);\s*}', '', obj)
    data = json.loads(obj)
    return {
        'id': song_id,
        'name': unquote(data['params']['name']),
        'artist': data['params']['artist'],
        'url': data['params']['filename'],
        'size': data['filesize']
    }

async def song(request: web.BaseRequest):
    args = await request.post()
    try:
        song_id = int(args.get('songID', ''))
    except ValueError:
        return web.Response(text='-1')

    song = None

    # if cache is enabled, check it first
    if CACHE:
        with db as c:
            song = c.execute('SELECT * FROM songs WHERE id=?', (song_id, )).fetchone()
            if song:
                song = {
                    'name': song[1],
                    'artist': song[2],
                    'size': song[3],
                    'url': song[4],
                }

    if not song:
        official = await get_song_official(song_id)
        if official != '-2':
            return web.Response(text=official)

    if CACHE:
        if not song:
            with db as c:
                song = await scrape_song_ng(song_id)
                if song:
                    c.execute('INSERT INTO songs (id, name, artist, size, url) VALUES (?, ?, ?, ?, ?)',
                        (song_id, song['name'], song['artist'], song['size'], song['url']))
    else:
        song = await scrape_song_ng(song_id)

    if not song:
        return web.Response(text='-1')

    stupid = {
        1: song_id,
        2: song['name'],
        3: 69, # (artist id) what is this even for
        4: song['artist'],
        5: f"{song['size'] / 1024 / 1024:.2f}",
        6: '',
        7: '',
        8: '0',
        10: quote(song['url'])
    }
    print(f"{song_id}: {song['name']} - {song['artist']}")
    sep = '~|~'
    return web.Response(text=sep.join(f'{key}{sep}{value}' for key, value in stupid.items()))

app = web.Application()

app.add_routes([
    web.post('/song', song),
])

web.run_app(app, port=int(sys.argv[1]) if len(sys.argv) > 1 else 8080)