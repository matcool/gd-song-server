# gd song server

A custom song server for geometry dash which scrapes the newgrounds audio portal, allowing you to use **any** song from newgrounds, whether its allowed on GD or not.

*you can't use this to download songs that have been removed from newgrounds entirely*
## Usage

```
python server.py [port]
```
`port` is optional and defaults to 8080

This will run the server on the given port, with the only available endpoint being `/song`. \
To actually use this in GD you can either change the song url using:
### MegaHack
Manually edit one of the jsons found in the `hacks/` folder (should work for both v5 and v6) and add this
```json
{
    "name": "My Own Song Bypass",
    "desc": "Allows the downloading of banned songs.",
    "opcodes": [
        {
            "addr": "0x2CDF44",
            "on": "<your encoded url> 00",
            "off": "68 74 74 70 3A 2F 2F 77 77 77 2E 62 6F 6F 6D 6C 69 6E 67 73 2E 63 6F 6D 2F 64 61 74 61 62 61 73 65 2F 67 65 74 47 4A 53 6F 6E 67 49 6E 66 6F 2E 70 68 70 00"
        }
    ]
}
```
To get your encoded url, run this bit of code
```py
>>> ' '.join(f'{ord(i):X}' for i in 'your url here')
'79 6F 75 72 20 75 72 6C 20 68 65 72 65'
```

### EXE Editing

You can also change the song url by editing the exe and replacing `http://www.boomlings.com/database/getGJSongInfo.php` with `http://your-server/song` (make sure the lengths match) \
*I haven't tested this myself so it may not work*