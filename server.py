from aiohttp import web, ClientSession
from urllib.parse import unquote, quote
import asyncio
import json
import re
import sqlite3
from bs4 import BeautifulSoup
import sys
import argparse
import time
import re
import os
import asyncio

parser = argparse.ArgumentParser()
parser.add_argument('port', nargs='?', default=8080, type=int)
parser.add_argument('--host', help='Host URL', default='http://localhost')
parser.add_argument('--yt', help='Enable youtube-dl support for custom songs', action='store_true')
args = parser.parse_args()

print(f'Running on {args.host}:{args.port} with youtube-dl support {"enabled" if args.yt else "disabled"}')

if 'win32' in sys.platform:
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

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
YOUTUBE_DL_COOLDOWN = 2 * 60
last_youtube_dl_use = time.time() - YOUTUBE_DL_COOLDOWN

re_dropbox = re.compile(r'https:\/\/www\.dropbox\.com\/s\/\w{15}\/.+')
re_soundcloud = re.compile(r'https:\/\/(?:www\.)?soundcloud\.com\/[\w-]+\/[\w-]+')
re_youtube = re.compile(r'https:\/\/(?:(?:www\.)?youtube\.com\/watch\?v=|youtu.be\/)([\w-]{11})')

with db as c:
    c.execute('CREATE TABLE IF NOT EXISTS songs (id integer primary key, name text, artist text, size int, url text, origin text)')
    c.execute('CREATE TABLE IF NOT EXISTS cache (id integer,             name text, artist text, size int, url text)')

# amazing migration
with db as c:
    columns = [i[1] for i in c.execute('pragma table_info(songs)').fetchall()]
    if 'origin' not in columns:
        c.execute('ALTER TABLE songs ADD origin text')

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

def add_custom_song(name: str, author: str, size: int, url: str, origin: str='') -> int:
    with db as c:
        return c.execute('INSERT INTO songs (name, artist, size, url, origin) VALUES (?, ?, ?, ?, ?)', (name, author, size, url, origin)).lastrowid

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

    youtube_dl = False

    if re_dropbox.match(url):
        url = url.replace('www.dropbox.com', 'dl.dropboxusercontent.com')
    # i wish i had the walrus operator
    elif re_soundcloud.match(url):
        url = re_soundcloud.match(url)[0]
        youtube_dl = True
    elif re_youtube.match(url):
        url = 'https://youtu.be/' + re_youtube.match(url)[1]
        youtube_dl = True

    if args.yt and youtube_dl:
        return await handle_youtube_dl(url)
    try:
        async with ClientSession() as session:
            async with session.head(url) as resp:
                c_type = resp.headers.get('Content-Type', '')
                c_length = resp.headers.get('Content-Length', '0')
                if not c_type.startswith('audio/'):
                    msg = f'content type is not audio ({c_type}), will probably not work'
                else:
                    msg = ''
                try:
                    size = int(c_length)
                except ValueError:
                    size = 0
    except:
        return missing_parameters()
    return json_response({'song_id': add_custom_song(name, author, size, url) + CUSTOM_SONG_OFFSET, 'message': msg})

async def run_command(*args):
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process, stdout, stderr

async def handle_youtube_dl(url: str):
    global last_youtube_dl_use
    cooldown = YOUTUBE_DL_COOLDOWN - (time.time() - last_youtube_dl_use)
    if cooldown > 0:
        return json_response({'error': True, 'message': f'youtube-dl is on cooldoown! please wait {cooldown:.0f}s'})
    last_youtube_dl_use = time.time()
    if not os.path.exists('downloaded'):
        os.mkdir('downloaded')
    print('downloading:', url)
    process, stdout, stderr = await run_command(
        'youtube-dl', '--print-json', '--extract-audio', '--audio-format', 'mp3', '--max-filesize', '20m', url,
        '--no-overwrites', '--output', 'downloaded/tmp.mp3'
    )
    if not process.returncode:
        data = json.loads(stdout.decode('utf-8'))
        name = data['title']
        artist = data['uploader']
        print('downloaded', name, artist)
        song_id = add_custom_song(name, artist, os.path.getsize('downloaded/tmp.mp3'), url='', origin=url)
        os.rename('downloaded/tmp.mp3', f'downloaded/{song_id}.mp3')
        with db as c:
            c.execute('UPDATE songs SET url=? WHERE id=?', (f'{args.host}:{args.port}/downloaded/{song_id}.mp3', song_id))
        return json_response({'song_id': song_id + CUSTOM_SONG_OFFSET})
    else:
        return json_response({'error': True, 'message': 'error when downloading'})

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

app.router.add_static('/downloaded', path='downloaded')

web.run_app(app, port=int(sys.argv[1]) if len(sys.argv) > 1 else 8080)
print('bye')
db.close()