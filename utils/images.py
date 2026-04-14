from discord.ext.commands import Bot
from config import CACHE_CHANNEL
import asyncio

async def proxy_image(urls:list, bot:Bot) -> list[str]:
	try:
		channel = bot.get_channel(CACHE_CHANNEL) or await bot.fetch_channel(CACHE_CHANNEL)
		msg = await channel.send('\n'.join(urls)) #type: ignore
		for _ in range(4):
			await asyncio.sleep(1)
			msg = await channel.fetch_message(msg.id) #type: ignore
			if msg.embeds: await msg.delete(); break
		return [(img.proxy_url or '').split('/external/')[1] for x in msg.embeds if (img := x.thumbnail or x.image)]
	except Exception as e: raise e

		# if msg.embeds and (img := (msg.embeds[0].thumbnail or msg.embeds[0].image)):
		# 	if img.proxy_url and '/external/' in img.proxy_url:
				
		# 		# if self.current_track == query:
		# 		# 	self.urls['cover'] = f"mp:external/{img.proxy_url.split('/external/')[1]}"
		# 		# 	self.last_sent_line = ""
		# 		# break