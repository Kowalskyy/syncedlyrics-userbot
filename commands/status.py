from config import CACHE_CHANNEL, DEFAULT_LINE, DEFAULT_COVER
from discord import Activity, ActivityType, ActivityButton
from discord.ext import commands, tasks
from utils import get_media_info
from logging import getLogger
import syncedlyrics
import asyncio
import httpx
import time

logger = getLogger('status')

class Status(commands.Cog):
	def __init__(self, bot:commands.Bot):
		self.bot = bot
		self.is_active = False

		self.current_track = ''
		self.current_lyrics = []
		self.last_sent_line = ""

		self.proxied_cover_url = None

		self.track_provider = None
		self.track_url = None
		self.track_duration = 0

		self.last_reported_pos = -1
		self.elapsed = 0.0
		self.last_tick = time.time()

	async def _fetch_lyrics(self, query: str):
		raw = await asyncio.to_thread(syncedlyrics.search, query, False, True, None, [])
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

	async def _fetch_and_proxy_cover(self, artist: str, title: str, expected_track: str):
		cover_url = None
		query = f'{artist} - {title}'

		headers = {"User-Agent": "Mozilla/5.0"}
		
		async with httpx.AsyncClient(headers=headers) as client:
			services = {
				'apple.music': {
					'base_url': 'https://itunes.apple.com/search',
					'params': {'term': query, 'entity': 'song', 'limit': 1, 'country': 'us'},
					'cover_path': ['results', 0, 'artworkUrl100'], 
					'duration_path': ['results', 0, 'trackTimeMillis'],
					'url_path': ['results', 0, 'trackViewUrl'],
					'result_key': 'resultCount'
				},
				'deezer': {
					'base_url': 'https://api.deezer.com/search',
					'params': {'q': query, 'limit': 1},
					'cover_path': ['data', 0, 'album', 'cover_xl'], 
					'duration_path': ['data', 0, 'duration'],
					'url_path': ['data', 0, 'link'],
					'result_key': 'total'
				}
			}
			try:
				for name, service in services.items():
					base_url, params, cpath, dpath, upath, rkey = service.values()
					rjson = (await client.get(base_url, params=params)).json()
					if rjson.get(rkey, 0) > 0:
						self.track_provider = name
						def walk(data, path):
							for k in path: data = data[k] if isinstance(data, list) else data.get(k, {})
							return data
						cover_url, self.track_duration, self.track_url = walk(rjson, cpath), walk(rjson, dpath), walk(rjson, upath)
						if name == 'apple.music': 
							cover_url = cover_url.replace('100x100', '1000x1000')
							self.track_duration /= 1000
							self.track_url = self.track_url.split('?')[0]
						if cover_url: logger.info(f'found info on {name}'); break
			except Exception as e: logger.error(f'cover not found due to {e}')

		if not cover_url or self.current_track != expected_track: logger.error(f'cover not found'); return
		
		try:
			channel = self.bot.get_channel(CACHE_CHANNEL) or await self.bot.fetch_channel(CACHE_CHANNEL)
			msg = await channel.send(cover_url) #type: ignore
			for _ in range(4):
				await asyncio.sleep(1)
				msg = await channel.fetch_message(msg.id) #type: ignore
				if msg.embeds and (img := (msg.embeds[0].thumbnail or msg.embeds[0].image)):
					if img.proxy_url and '/external/' in img.proxy_url:
						if self.current_track == expected_track:
							self.proxied_cover_url = f"mp:external/{img.proxy_url.split('/external/')[1]}"
							self.last_sent_line = ""
						break
			await msg.delete()
		except Exception as e: logger.error(f"proxy error: {e}")

	@commands.command()
	async def lyrics(self, c:commands.Context):
		await c.message.delete()
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
		info = await get_media_info()
		if not info: return

		artist, title = info['artist'], info['title']
		full_name = f'{artist} - {title}'

		# new track handler
		if self.current_track != full_name:
			self.current_track = full_name
			self.current_lyrics = []
			self.last_sent_line = ""
			self.proxied_cover_url = None
			self.track_provider = None
			self.track_url = None
			self.track_duration = 0
			self.last_reported_pos = -1
			self.elapsed = 0.0
			self.last_tick = time.time()

			asyncio.create_task(self._fetch_lyrics(full_name))
			asyncio.create_task(self._fetch_and_proxy_cover(artist, title, full_name))
	
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
				state=title[:128],
				timestamps=ts_payload, #type: ignore it's fine as long discord doesn't change shit
				assets = {
					'large_image': self.proxied_cover_url if self.proxied_cover_url else f'mp:external/{DEFAULT_COVER}',
					'large_text': f'by {artist}'[:128]
				},
				buttons = [ActivityButton(f'listen on {self.track_provider}', self.track_url)] if self.track_provider and self.track_url else [] 
			)
			await self.bot.change_presence(activity=activity)

	@lyrics_loop.before_loop
	async def before_lyrics(self): await self.bot.wait_until_ready()

async def setup(bot:commands.Bot):
	await bot.add_cog(Status(bot))
