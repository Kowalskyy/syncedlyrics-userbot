from discord import Activity, ActivityType, ActivityButton
from config import DEFAULT_LINE, DEFAULT_COVER
from discord.ext import commands, tasks
from logging import getLogger
from fuzzywuzzy import fuzz
import syncedlyrics
import asyncio
import httpx
import utils
import time

logger = getLogger('status')
PITCH_CLASSES = {-1: '?', 0: 'C', 1: 'C♯ / D♭', 2: 'D', 3: 'D♯ / E♭', 4: 'E', 5: 'F', 6: 'F♯ / G♭', 7: 'G', 8: 'G♯ / A♭', 9: 'A', 10: 'A♯ / B♭', 11: 'B'} #idk where do i put it, let it be here

class Status(commands.Cog):
	def __init__(self, bot:commands.Bot):
		self.bot = bot
		self.is_active = False

		self.current_track = ''
		self.current_lyrics = []
		self.last_sent_line = ""

		self.track_provider = None
		self.track_duration = 0
		self.track_isrc = ''

		self.last_reported_pos = -1
		self.elapsed = 0.0
		self.last_tick = time.time()

		self.urls = {}
		self.stats = {}
		self.create_stats = True

	async def _fetch_lyrics(self, query: str):
		raw = await asyncio.to_thread(syncedlyrics.search, query, False, True, None, ['Musixmatch', 'Lrclib', 'NetEase', 'Megalobiz'])
		if not raw or self.current_track != query: return
		lyrics = []
		for line in raw.splitlines():
			try:
				time, lyric = line[1:].split(']', 1); lyric = lyric.strip()
				if not lyric: continue # in case empty line
				m, s = map(float, time.split(':')); t = m * 60 + s
				if lyrics and t - lyrics[-1][0] < 4.2: lyrics[-1][1] += f" / {lyric}"
				else: lyrics.append([t, lyric])
			except: continue
		self.current_lyrics = lyrics

	async def _fetch_and_proxy_data(self, query:str):
		cover_url = None

		headers = {"User-Agent": "Mozilla/5.0"}
		
		async with httpx.AsyncClient(headers=headers) as client:
			services = {
				'deezer': {
					'base_url': 'https://api.deezer.com/search',
					'params': {'q': query, 'limit': 1},
					'cover_path': ['data', 0, 'album', 'cover_xl'], 
					'duration_path': ['data', 0, 'duration'],
					'track_url_path': ['data', 0, 'link'],
					'artist_url_path': ['data', 0, 'artist', 'link'],
					'album_url_path': ['data', 0, 'album', 'id'],
					'track_name': ['data', 0, 'title'],
					'artist_name': ['data', 0, 'artist', 'name'],
					'result_key': 'total'
				},
				'apple.music': {
					'base_url': 'https://itunes.apple.com/search',
					'params': {'term': query, 'entity': 'song', 'limit': 1, 'country': 'us'},
					'cover_path': ['results', 0, 'artworkUrl100'], 
					'duration_path': ['results', 0, 'trackTimeMillis'],
					'track_url_path': ['results', 0, 'trackViewUrl'],
					'artist_url_path': ['results', 0, 'artistViewUrl'],
					'album_url_path': ['results', 0, 'collectionViewUrl'],
					'track_name': ['results', 0, 'trackName'],
					'artist_name': ['results', 0, 'artistName'],
					'result_key': 'resultCount'
				}
			}
			for name, service in services.items():
				base_url, params, coverp, durationp, trackp, artistp, albump, tname, aname, rkey = service.values()
				try:
					rjson = (await client.get(base_url, params=params)).json()
					if rjson.get(rkey, 0) > 0:
						def walk(data, path):
							for k in path: data = data[k] if isinstance(data, list) else data.get(k, {})
							return data

						if not fuzz.ratio(f'{walk(rjson, aname)} - {walk(rjson, tname)}', query) >= 60: continue # somewhy deezer api sucks at searching

						self.track_provider = name
						cover_url, self.track_duration = walk(rjson, coverp), walk(rjson, durationp)
						self.urls = {
							'track': walk(rjson, trackp),
							'artist': walk(rjson, artistp),
							'album': walk(rjson, albump)
						}
						if name == 'apple.music': 
							cover_url = cover_url.replace('100x100', '1000x1000')
							self.track_duration /= 1000
							self.urls['track'] = self.urls['track'].split('?')[0]
						if name == 'deezer': self.urls['album'], self.track_isrc = f"https://www.deezer.com/album/{self.urls['album']}", rjson.get('data')[0]['isrc']
						if cover_url: logger.info(f'found info on {name}'); break
				except Exception as e: logger.error(f'cover not found on {name} due to {e}')

		if not cover_url or self.current_track != query: logger.error(f'cover not found'); return

		try:
			urls = [cover_url]
			if self.track_isrc and (url := await self._fetch_mood()): urls.append(url)
			proxified_urls = await utils.proxy_image(urls, self.bot)
			self.urls['cover'] = f'mp:external/{proxified_urls[0]}'
			if len(proxified_urls) >= 2: self.urls['small_image'] = f'mp:external/{proxified_urls[1]}'
			self.last_sent_line = 'covers!'
		except Exception as e: logger.error(f"proxy error: {e}")

	async def _fetch_mood(self):
		if not self.create_stats: return None
		base_url = 'https://api.reccobeats.com/v1/track'

		async with httpx.AsyncClient() as client:
			rbid = ((await client.get(f'{base_url}?ids={self.track_isrc}')).json().get('content', [{}]) or [{}])[0].get('id', '')
			if not rbid: return
			data = (await client.get(f'{base_url}/{rbid}/audio-features')).json()
			_, __, ___, a, d, e, i, k, l, ld, m, s, t, v = data.values()
			self.stats = data
			# L = max(0.2, (ld + 20) / 20) * 255
			# return "{:02x}{:02x}{:02x}".format(*[int(max(0, min(1, v)) * L) for v in (e - a/2, v * (1 if m==0 else 0.3), a + (1 - e)/2)])
			L = max(0.2, (ld + 20) / 20) * 255
			color_hex = "{:02x}{:02x}{:02x}".format(*[int(max(0, min(1, v)) * L) for v in (e - a/2, v * (1 if m==0 else 0.3), a + (1 - e)/2 + s + max(0, 0.2 - v))])

			chart_data = {
				'type': 'radar',
				'data': {
					'labels': ['' for _ in range(8)],
					'datasets': [{
						'data': [a,d,e,i,l,max(0, min(1, (ld + 60) / 60)),s,v],
						'backgroundColor': f'rgba({",".join([str((int(color_hex[i:i+2],16))) for i in range(0,5,2)])},0.9)',
						'borderColor': f'rgb({",".join([str(((c:=int(color_hex[i:i+2],16))+(255-c)//3)) for i in range(0,5,2)])})', 'borderWidth': 3, 'pointRadius': 0
					}]
				},
				'options': {
					'legend': {'display': False},
					'scale': {
						'display': True,
						'ticks': {'display': False, 'min': 0, 'max': 1, 'stepSize': 0.33},
						'gridLines': {'color': 'rgba(255,255,255,0.6)', 'lineWidth':2},
						'angleLines': {'color': 'rgba(255,255,255,0.3)', 'lineWidth': 2},
						'pointLabels': {'display': False}
					}
				}
			}

			resp = await client.post("https://quickchart.io/chart/create", json={"chart": chart_data,"width": 128,"height": 128,"format": "png","backgroundColor": "transparent"})
			if resp.status_code == 200: return resp.json().get('url')
			return ""

	@commands.command()
	async def lyrics(self, c:commands.Context):
		await c.message.delete()
		argument = c.message.content.removeprefix('.lyrics').strip()
		match argument:
			case 'stats' | 'features' | 'web':
				logger.info(f'audio-features fetching {"disabled" if self.create_stats else "enabled"}')
				self.create_stats = not self.create_stats
			case _:
				if self.is_active:
					self.is_active = False
					self.lyrics_loop.stop()
					await self.bot.change_presence(activity=None)
					logger.info("Lyrics disabled")
				else:
					self.is_active = True; self.current_track = ""
					self.lyrics_loop.start()
					logger.info("Lyrics enabled")

	@tasks.loop(seconds=1)
	async def lyrics_loop(self):
		info = await utils.get_media_info()
		if not info: 
			self.is_active = False; self.lyrics_loop.stop(); await self.bot.change_presence(activity=None) # type: ignore
			logger.info('Lyrics disabled due to no active SMTC sessions'); return

		artist, title = info['artist'], info['title']
		if not artist and not title: return
		full_name = f'{artist} - {title}'

		# new track handler
		if self.current_track != full_name:
			self.current_track = full_name
			self.current_lyrics = []
			self.last_sent_line = ""
			self.track_provider = None
			self.track_duration = 0
			self.track_isrc = ''
			self.last_reported_pos = -1
			self.elapsed = 0.0
			self.last_tick = time.time()
			self.urls = {}
			self.stats = {}

			asyncio.create_task(self._fetch_lyrics(full_name))
			asyncio.create_task(self._fetch_and_proxy_data(full_name))

		#timer
		now = time.time()
		delta = now - getattr(self, 'last_tick', now)
		self.last_tick = now

		if info['status'] == 5: return

		if info['position'] != getattr(self, 'last_reported_pos', -1):
			self.last_reported_pos = info['position']
			self.elapsed = info['position']
		else:
			self.elapsed += delta

		#line selector
		current_line = DEFAULT_LINE
		if self.current_lyrics:
			for ts, text in self.current_lyrics:
				if self.elapsed >= ts: current_line = text
				else: break

		#da updater
		if current_line != self.last_sent_line:
			self.last_sent_line = current_line

			#da timestamper
			now_ms = int(now * 1000)
			start_time = now_ms - int(self.elapsed * 1000)
			duration = info['duration'] or self.track_duration
			end_time = start_time + int(duration * 1000) if duration > 0 else None

			ts_payload = {'start': start_time}
			if end_time: ts_payload['end'] = end_time

			#da activitinator
			activity = Activity(
				type = ActivityType.listening, 
				application_id=1295028329069674609,
				name = f'{title} by {artist}'[:128],
				details = f'🎤 {current_line}'[:128],
				details_url = self.urls.get('album', '') if self.urls.get('album', '') else None,
				state=title[:128],
				state_url=self.urls.get('track', '') if self.urls.get('track', '') else None,
				timestamps=ts_payload, #type: ignore it's fine as long discord doesn't change shit
				assets = {
					'large_image': self.urls.get('cover', '') if self.urls.get('cover', '') else f'mp:external/{DEFAULT_COVER}',
					'large_text': f'by {artist}'[:128],
					'large_url': self.urls.get('artist', '') if self.urls.get('artist', '') else None, # type: ignore
					'small_image': self.urls.get('small_image', '') if self.urls.get('small_image', '') else None,
					'small_text': f'BPM: {int(self.stats["tempo"])}\nKey: {PITCH_CLASSES.get(self.stats["key"])} {"Major" if self.stats["mode"] == 1 else "Minor"}' if self.stats else None
				}
			)
			await self.bot.change_presence(activity=activity)

	@lyrics_loop.before_loop
	async def before_lyrics(self): await self.bot.wait_until_ready()

async def setup(bot:commands.Bot):
	await bot.add_cog(Status(bot))
