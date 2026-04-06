from discord.ext import commands
from logging import getLogger
from config import GIF_NAME
from discord import File
from io import BytesIO

logger = getLogger('img2gif')

class img2gif(commands.Cog):
	def __init__(self, bot:commands.Bot):
		self.bot = bot

	@commands.command()
	async def gif(self, c:commands.Context):
		await c.message.delete()
		attachment = None

		if c.message.attachments: attachment = c.message.attachments[0]
		elif c.message.reference:
			try:
				rmsg = await c.fetch_message(c.message.reference.message_id or 0)
				if rmsg.attachments: attachment = rmsg.attachments[0]
			except Exception as e:
				logger.error(e); return
		else: logger.warning(f'no attachments were found'); return

		if not attachment: logger.warning(f'no attachments were found'); return 

		try:
			logger.debug(f'found attachment: {attachment.url}')
			adata = await attachment.read()
			new_data = BytesIO(adata)
			logger.debug(f'success')
			return await c.send(file=File(new_data, GIF_NAME))
		except Exception as e: logger.error(e); return

async def setup(bot:commands.Bot):
	await bot.add_cog(img2gif(bot))
