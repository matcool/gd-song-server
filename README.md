# gd song server

A song server for Geometry Dash with two extra features

## Newgrounds Bypass

This song server will allow you to use **any** song from newgrounds, whether it's allowed in GD or not.

*you can't use this to download songs that have been removed from newgrounds*

## Custom Songs

You can add custom songs by providing a direct link to a mp3 file (from Dropbox for example). The page to do so is accessible from `http://localhost:port/`

![screenshot of the main page](https://i.imgur.com/WM4yWEE.png)

To change the song offset (defaults to 4000000), edit this line in `server.py`
```py
CUSTOM_SONG_OFFSET = 4_000_000
```

## Usage

```
python server.py [port]
```
`port` is optional and defaults to 8080

To actually use this in GD, you'll need to replace the default song endpoint. To do that you can either:

### MegaHack

Manually edit one of the jsons found in the `hacks/` folder (should work for both v5 and v6) and add this
```json
{
    "name": "My Own Song Server",
    "desc": "something",
    "opcodes": [
        {
            "addr": "0x2CDF44",
            "on": "<your encoded url> 00",
            "off": "68 74 74 70 3A 2F 2F 77 77 77 2E 62 6F 6F 6D 6C 69 6E 67 73 2E 63 6F 6D 2F 64 61 74 61 62 61 73 65 2F 67 65 74 47 4A 53 6F 6E 67 49 6E 66 6F 2E 70 68 70 00"
        }
    ]
}
```
To get your encoded url, run this bit of code (replace localhost with your actual url)
```py
>>> ' '.join(f'{ord(i):X}' for i in 'http://localhost:8080/song')
'68 74 74 70 3A 2F 2F 6C 6F 63 61 6C 68 6F 73 74 3A 38 30 38 30 2F 73 6F 6E 67'
```

### EXE Editing

You can also change the song url by editing the exe and replacing `http://www.boomlings.com/database/getGJSongInfo.php` with `http://your-server/song` (make sure the lengths match) \
*you'll have to edit the exe again to go back to default*
