from aiohttp import web, ClientSession
from urllib.parse import unquote, quote
import asyncio
import json
import re
from bs4 import BeautifulSoup

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
        return web.Response(text='-1')
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

    official = await get_song_official(song_id)
    if official != '-2':
        return web.Response(text=official)
    
    song = await scrape_song_ng(song_id)

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

web.run_app(app, port=8080)