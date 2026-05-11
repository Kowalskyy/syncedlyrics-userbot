from discord.ext import commands, tasks
from config import DEFAULT_LINE
from logging import getLogger
import syncedlyrics
import asyncio
import httpx
import utils
import time

logger = getLogger('status')

class Status(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.settings = {
			'is_active': False,
			'track_statistics': True,
			# 'stream_to_status': False
		}
		
		self.current_track = ''
		self.track = {} # title:str, artist:str, album:str, isrc:str, duration:int, provider:str (deezer/apple.music), 
		# ^ urls:dict (track_url:str, album_url:str, artist_url:str, cover_url:str, proxified_cover_url:str, small_image:str, proxified_small_image:str)
		# ^ statistics (acousticness:int, danceability:int, energy:int, instrumentalness:int, key:int, liveness:int, loudness:int, mode:int, speechiness:int, tempo:int, valence:int)
		self.found_lyrics = [] # list(tuple[timestamp:int, lyric:str])
		self.last_sent_line = ''

		self.last_reported_pose = -1
		self.elapsed = 0.0
		self.last_tick = time.time()

	async def _fetch_lyrics(self, query:str):
		raw = await asyncio.to_thread(syncedlyrics.search, query, False, True, None, ['Musixmatch', 'Lrclib', 'NetEase', 'Megalobiz'])
		if (not raw) or (self.current_track != query): return
		lyrics = []
		for line in raw.splitlines():
			try:
				time, lyric = line[1:].split(']', 1); lyric = lyric.strip()
				if not lyric: continue # in case empty line
				m, s = map(float, time.split(':')); t = m * 60 + s
				if lyrics and t - lyrics[-1][0] < 4.2: lyrics[-1][1] += f" / {lyric}"
				else: lyrics.append([t, lyric])
			except: continue
		self.found_lyrics = lyrics

	async def _fetch_track_info(self, title:str, artist:str):
		query = f'{artist} {title}'
		async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
			services = {
				'deezer': {'url': 'https://api.deezer.com/search', 'params': {'q': query, 'limit': 1}},
				'apple.music': {'url': 'https://itunes.apple.com/search', 'params': {'term': query, 'entity': 'song', 'limit': 1, 'country': 'us'}}
			}
			for service, data in services.items():
				try:
					req_json:dict = (await client.get(**data)).json()
					if any(req_json.get(key, 0) > 0 for key in ['total', 'resultCount']):
						if info := utils.build_track_info(req_json, service, artist, title): self.track = info; logger.info(f'Found information on {service}'); break
					logger.info(f'No information about track on {service} were found.')
				except Exception as e: logger.error(f'Error fetching track info: {e if e else "httpx sucking dick"}.')

			if self.settings['track_statistics'] and self.track.get('isrc', ''): self.track['urls']['small_image'] = await self._fetch_track_stats(client)
		try:
			images = []
			if cover := self.track['urls'].get('cover_url', None): images.append(cover)
			if small_image := self.track['urls'].get('small_image', None): images.append(small_image)
			if not images: return
			proxified_images = await utils.proxy_image(images, self.bot)
			self.track['urls']['proxified_cover_url'] = proxified_images[0]
			if len(proxified_images) >= 2: self.track['urls']['proxified_small_image'] = proxified_images[1]
			self.last_sent_line = 'covers!'
		except Exception as e: logger.error(f'Error proxifying images: {e}')
		if not self.track.get('statistics', {}): self.track['statistics'] = {}

	async def _fetch_track_stats(self, client:httpx.AsyncClient):
		try:
			self.track['statistics'] = {}
			if not (data := ((await client.get(f'https://api.reccobeats.com/v1/audio-features?ids={self.track["isrc"]}')).json().get('content', []) or [{}])[0]): return ''
			for k in ('id', 'href', 'isrc'): data.pop(k, None)
			self.track['statistics'] = data
			a, d, en, i, key, l, ld, m, s, t, v = data.values()
			color = [str(int(max(0, min(1, val)) * max(0.2, (ld + 20) / 20) * 255)) for val in (en - a/2, v * (1 if m==0 else 0.3), a + (1 - en)/2 + s + max(0, 0.2 - v))]
			chart_data = {
				'type': 'radar',
				'data': {
					'labels': ['' for _ in range(8)],
					'datasets': [{
						'data': [a,d,en,i,l,max(0, min(1, (ld + 60) / 60)),s,v],
						'backgroundColor': f'rgba({",".join(color)},0.9)',
						'borderColor': f'rgb({",".join(color)})', 'borderWidth': 3, 'pointRadius': 0
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
			return ''
		except Exception as e: logger.error(f'Error fetching track statistics: {e}'); return ''

	@commands.command()
	async def lyrics(self, c:commands.Context):
		argument = c.message.content.removeprefix('.lyrics').strip()
		s = self.settings

		match argument.lower():
			case 'stats' | 'features' | 'web' | 'statistics': s['track_statistics'] = not s['track_statistics']; await c.message.delete(); logger.info(f'Fetching track statistics {"en" if s["track_statistics"] else "dis"}abled')
			# case 'status': s['stream_to_status'] = not s['stream_to_status']; await c.message.delete(); logger.info(f'Streaming to status {"en" if s["stream_to_status"] else "dis"}abled')
			case '':
				await c.message.delete()
				s['is_active'] = not s['is_active']
				if s['is_active']: self.track = {}; self.lyrics_loop.start(); logger.info('Lyrics enabled.')
				else: self.lyrics_loop.stop(); await self.bot.change_presence(activity=None); logger.info('Lyrics disabled.')
			case 'settings' | 'cfg' | _: return await c.message.edit(content=f'Currently {"enabled" if s["is_active"] else "disabled"}.\n'
									   f'Small image a.k.a. track statistics {"enabled" if s["track_statistics"] else "disabled"} (.stats/.web/.features).')
									#    f'Status streaming {"enabled" if s["stream_to_status"] else "disabled"} (.status).')	

	@tasks.loop(seconds=1)
	async def lyrics_loop(self):
		info = await utils.get_media_info()
		if not info: 
			self.is_active = False; self.lyrics_loop.stop(); await self.bot.change_presence(activity=None) # type: ignore
			logger.info('Lyrics disabled due to no active SMTC sessions'); return

		artist, title = info['artist'], info['title']
		if not artist and not title: return
		query = f'{artist} - {title}'

		# new track handler
		if self.current_track != query:
			self.current_track = query
			self.track = {
				'title': title,
				'artist': artist,
				'album': '',
				'isrc': '',
				'duration': 0,
				'provider': '',
				'urls': {},
				'statistics': {}
			}
			self.found_lyrics = []
			self.last_sent_line = ''
			self.last_reported_pose = -1
			self.elapsed = 0.0
			self.last_tick = time.time()

			asyncio.create_task(self._fetch_lyrics(query))
			asyncio.create_task(self._fetch_track_info(title, artist))

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
		if self.found_lyrics:
			for ts, text in self.found_lyrics:
				if self.elapsed >= ts: current_line = text
				else: break

		#da updater
		if current_line != self.last_sent_line:
			self.last_sent_line = current_line

			#da timestamper
			now_ms = int(now * 1000)
			start_time = now_ms - int(self.elapsed * 1000)
			duration = info['duration'] or self.track.get('duration', 0)
			end_time = start_time + int(duration * 1000) if duration > 0 else None

			ts_payload = {'start': start_time}
			if end_time: ts_payload['end'] = end_time

			await self.bot.change_presence(activity=utils.build_activity(self.track, current_line, self.found_lyrics, ts_payload))

	@lyrics_loop.before_loop
	async def before_lyrics(self): await self.bot.wait_until_ready()

async def setup(bot:commands.Bot):
	await bot.add_cog(Status(bot))
