# syncedlyrics-userbot

syncs live lyrics to your discord status from basically anything running on your windows machine (spotify, browser, whatever that has SMTC support). and some fun features.

## features
- synced lyrics via listening activity (like spotify)
- automatic cover art search from apple music/deezer
- working covers via discord proxy
- includes some extra utility brainrot (a.k.a. some fun features)

## functionality
- status: the main lyric engine
- react: reacts to messages with regional indicators
- img2gif: converts/re-uploads images as gifs
- utils: gets channel ids and proxy urls

## setup
1. install requirements:
   `pip install discord.py-self syncedlyrics httpx python-dotenv`
2. create a `.env` file and put your token there:
   `USER_AUTH='your_token_here'`
3. change cache_channel id in `config.py`
4. run `python main.py`

## commands
- `.lyrics` - toggle the lyric status
- `.react <text>` - reacts to the replied message with letters
- `.gif` - converts replied image to gif
- `.cid` - gets current channel id (use it before using .lyrics PLEASE)
- `.url` - extracts proxy urls from embeds

## customization
customization is made in the `config.py` file
- GIF_NAME - name that will be used for every converted gif
- DEFAULT_LINE - text that will appear if no lyrics will be found
- DEFAULT_COVER - cover that will be used if track wasn't found neither on apple music nor on deezer (case where `.url` comes handy)

## disclaimer
self-bots are against discord tos. use it at your own risk. don't be a clown.

## credits
syncedlyrics for the heavy lifting.

me for the not killing myself

mxrengine for motivating me to make this public

hoyoverse for making honkai: star rail
