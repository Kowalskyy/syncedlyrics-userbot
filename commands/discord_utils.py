from discord.ext import commands
from logging import getLogger
from asyncio import sleep

logger = getLogger('utils')

class Utils(commands.Cog):
	def __init__(self, bot:commands.Bot):
		self.bot = bot

	@commands.command()
	async def cid(self, c:commands.Context):
		await c.message.edit(content=str(c.channel.id))
	
	@commands.command()
	async def url(self, c:commands.Context):
		if not c.message.reference or not c.message.reference.message_id: return await c.message.delete()

		rmsg = await c.channel.fetch_message(c.message.reference.message_id)
		if not rmsg.embeds: logger.warning('no embeds in replied message'); return await c.message.delete()

		ids = "\n".join([((embed.image or embed.thumbnail).proxy_url or '').split('/external/')[1] for embed in rmsg.embeds])
		
		await c.message.edit(content=f'```{ids}```')

async def setup(bot:commands.Bot):
	await bot.add_cog(Utils(bot))
