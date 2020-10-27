from aiohttp import web, ClientSession
from urllib.parse import unquote
import asyncio
import json
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

db = DBConnect('songs.db')
CUSTOM_SONG_OFFSET = 4_000_000

with db as c:
    c.execute('CREATE TABLE IF NOT EXISTS songs (id integer primary key, name text, author_name text, size int, url text)')

async def get_song_official(song_id: int):
    async with ClientSession() as session:
        async with session.post(f'http://www.boomlings.com/database/getGJSongInfo.php', data={'songID': song_id, 'secret': 'Wmfd2893gb7'}) as resp:
            return await resp.text()

def get_song_custom(song_id: int):
    c = db.conn.cursor()
    return c.execute('SELECT * FROM songs where id=?', (song_id, )).fetchone()

def get_all_songs():
    c = db.conn.cursor()
    return c.execute('SELECT * FROM songs').fetchall()

def add_custom_song(name: str, author: str, size: int, url: str) -> int:
    with db as c:
        return c.execute('INSERT INTO songs (name, author_name, size, url) VALUES (?, ?, ?, ?)', (name, author, size, url)).lastrowid

def fancy_song(song):
    return {
        'id': CUSTOM_SONG_OFFSET + song[0],
        'name': song[1],
        'author': song[2],
        'size': song[3],
        'url': song[4]
    }

def json_response(obj):
    return web.Response(text=json.dumps(obj), content_type='application/json')

def missing_parameters():
    return web.Response(status=422)

async def song(request: web.BaseRequest):
    args = await request.post()
    try:
        song_id = int(args['songID'])
    except ValueError:
        return web.Response(text='-1')

    if song_id <= CUSTOM_SONG_OFFSET:
        return web.Response(text=await get_song_official(song_id))

    song = fancy_song(get_song_custom(song_id - CUSTOM_SONG_OFFSET))

    stupid = {
        1: song['id'],
        2: song['name'],
        3: 69, # (author id) what is this even for
        4: song['author'],
        5: f"{song['size'] / 1024 / 1024:.2f}",
        6: '',
        7: '',
        8: '0',
        10: song['url']
    }
    sep = '~|~'
    return web.Response(text=sep.join(f'{key}{sep}{value}' for key, value in stupid.items()))

async def upload_get(request):
    return web.FileResponse('./upload.html')

async def upload(request: web.BaseRequest):
    data = await request.json()
    name = data.get('name', '').strip()
    author = data.get('author', '').strip()
    url = data.get('url', '').strip()
    if not name or not author or not url:
        return missing_parameters()
    # check if its actually an audio file and get the size
    if True:
        try:
            async with ClientSession() as session:
                async with session.head(url) as resp:
                    c_type = resp.headers.get('Content-Type', '')
                    c_length = resp.headers.get('Content-Length', '0')
                    if not c_type.startswith('audio/'): return missing_parameters()
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
    return json_response([fancy_song(song) for song in get_all_songs()])

async def index(request: web.BaseRequest):
    return web.FileResponse('./index.html')

app = web.Application()

app.add_routes([
    web.post('/song', song),
    web.get('/upload', upload_get),
    web.post('/upload', upload),
    web.get('/songs', songs),
    web.get('/', index),
])

# def error_pages(overrides):
#     async def middleware(app, handler):
#         async def middleware_handler(request):
#             try:
#                 response = await handler(request)
#                 override = overrides.get(response.status)
#                 if override is None:
#                     return response
#                 else:
#                     return await override(request, response)
#             except web.HTTPException as ex:
#                 override = overrides.get(ex.status)
#                 if override is None:
#                     raise
#                 else:
#                     return await override(request, ex)
#         return middleware_handler
#     return middleware

# async def handle_404(request, response):
#     print(request)
#     return response

# app.middlewares.append(error_pages({404: handle_404}))

web.run_app(app, port=8080)
print('bye')
db.close()