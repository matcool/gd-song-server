# gd song server

![screenshot of the main page](https://i.imgur.com/WM4yWEE.png)
*make sure the song url is a direct link to an audio file* \

custom song server with custom song support

## Usage

*Starting the server and installation is the same as [newgrounds branch](https://github.com/matcool/gd-song-server/tree/newgrounds#usage)*

Go to `http://localhost:8080/` to see all songs and upload new ones

To change the song offset (defaults to 4000000), edit this line in `server.py`
```py
CUSTOM_SONG_OFFSET = 4_000_000
```