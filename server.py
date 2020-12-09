from aiohttp import web, ClientSession
from urllib.parse import unquote, quote
import asyncio
import json
import re
import sqlite3
from bs4 import BeautifulSoup
import sys

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

db = DBConnect('songs.db')
CUSTOM_SONG_OFFSET = 4_000_000

with db as c:
    c.execute('CREATE TABLE IF NOT EXISTS songs (id integer primary key, name text, artist text, size int, url text)')
    c.execute('CREATE TABLE IF NOT EXISTS cache (id integer,             name text, artist text, size int, url text)')

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

def get_song_custom(song_id: int):
    c = db.conn.cursor()
    return c.execute('SELECT * FROM songs where id=?', (song_id, )).fetchone()

def get_all_songs():
    c = db.conn.cursor()
    return c.execute('SELECT * FROM songs').fetchall()

def add_custom_song(name: str, author: str, size: int, url: str) -> int:
    with db as c:
        return c.execute('INSERT INTO songs (name, artist, size, url) VALUES (?, ?, ?, ?)', (name, author, size, url)).lastrowid

def format_custom_song(song):
    return {
        'id': CUSTOM_SONG_OFFSET + song[0],
        'name': song[1],
        'artist': song[2],
        'size': song[3],
        'url': song[4]
    }

def json_response(obj):
    return web.Response(text=json.dumps(obj), content_type='application/json')

def missing_parameters():
    return web.Response(status=422)

def format_song_stupid(song) -> str:
    """Format a song to robtop's stupid formatting"""
    stupid = {
        1: song['id'],
        2: song['name'],
        3: 69, # (author id) what is this even for
        4: song['artist'],
        5: f"{song['size'] / 1024 / 1024:.2f}",
        6: '',
        7: '',
        8: '0',
        10: quote(song['url'])
    }
    sep = '~|~'
    return sep.join(f'{key}{sep}{str(value).replace(sep, "")}' for key, value in stupid.items())

async def song(request: web.BaseRequest):
    args = await request.post()
    try:
        song_id = int(args['songID'])
    except (ValueError, KeyError):
        return web.Response(text='-1')

    if song_id <= CUSTOM_SONG_OFFSET:
        return await handle_ng_song(song_id)

    song = format_custom_song(get_song_custom(song_id - CUSTOM_SONG_OFFSET))

    return web.Response(text=format_song_stupid(song))

async def handle_ng_song(song_id: int):
    song = None

    with db as c:
        song = c.execute('SELECT * FROM cache WHERE id=?', (song_id, )).fetchone()
        if song:
            song = {
                'id': song_id,
                'name': song[1],
                'artist': song[2],
                'size': song[3],
                'url': song[4],
            }

    if not song:
        official = await get_song_official(song_id)
        if official != '-2':
            return web.Response(text=official)

    if not song:
        with db as c:
            song = await scrape_song_ng(song_id)
            if song:
                c.execute('INSERT INTO cache (id, name, artist, size, url) VALUES (?, ?, ?, ?, ?)',
                    (song_id, song['name'], song['artist'], song['size'], song['url']))

    if not song:
        return web.Response(text='-1')

    return web.Response(text=format_song_stupid(song))

async def upload(request: web.BaseRequest):
    data = await request.json()
    name = data.get('name', '').strip().replace('~|~', '')
    author = data.get('author', '').strip().replace('~|~', '')
    url = data.get('url', '').strip().replace('~|~', '')
    if not name or not author or not url:
        return missing_parameters()
    # check if its actually an audio file and get the size
    if True:
        try:
            async with ClientSession() as session:
                async with session.head(url) as resp:
                    c_type = resp.headers.get('Content-Type', '')
                    c_length = resp.headers.get('Content-Length', '0')
                    # dropbox returns text/html, even though it works, so disabling it for now
                    # if not c_type.startswith('audio/'): return missing_parameters()
                    try:
                        size = int(c_length)
                    except ValueError:
                        size = 0
        except:
            return missing_parameters()
    else:
        size = 0
    return json_response({'song_id': add_custom_song(name, author, size, url) + CUSTOM_SONG_OFFSET})

async def songs(request: web.BaseRequest):
    return json_response([format_custom_song(song) for song in get_all_songs()])

async def index(request: web.BaseRequest):
    return web.FileResponse('./index.html')

app = web.Application()

app.add_routes([
    web.post('/song', song),
    web.post('/upload', upload),
    web.get('/songs', songs),
    web.get('/', index),
])

web.run_app(app, port=int(sys.argv[1]) if len(sys.argv) > 1 else 8080)
print('bye')
db.close()