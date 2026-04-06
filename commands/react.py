from discord.ext import commands
from logging import getLogger
from asyncio import sleep

logger = getLogger('react')
ru_to_en = {'а':'a', 'б':'b', 'в':'v', 'г':'g', 'д':'d', 'е':'e', 'ж':'j', 'з':'z', 
			'и':'i', 'к':'k', 'л':'l', 'м':'m', 'н':'n', 'о':'o', 'п':'p', 'р':'r', 
			'с':'s', 'т':'t', 'у':'u', 'ф':'f', 'х':'h', 'ц':'c', 'ч':'q', 'ш':'w', 
			'ы':'y', 'э':'e'}

class React(commands.Cog):
	def __init__(self, bot:commands.Bot):
		self.bot = bot

	@commands.command()
	async def react(self, c:commands.Context, argument: str):
		await c.message.delete()
		if not argument: return logger.warning('no text was passed')
		if not c.message.reference: return logger.warning('no message was replied')

		unique_letters = ''
		for l in argument.lower():
			if l in ru_to_en: l = ru_to_en[l]
			if l in 'abcdefghijklmnopqrstuvwxyz' and l not in unique_letters: unique_letters += l
		try:
			rmsg = await c.channel.fetch_message(c.message.reference.message_id or 0)
			for l in unique_letters:
				await rmsg.add_reaction(chr(127462 - ord('a') + ord(l))) # by Gemini 3.1 Pro on https://aistudio.google.com
				await sleep(.5)

		except Exception as e:
			logger.error(e)

async def setup(bot:commands.Bot):
	await bot.add_cog(React(bot))
