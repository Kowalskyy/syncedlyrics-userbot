from discord.ext import commands
from logging import getLogger
from config import TOKEN
import asyncio
import os

bot = commands.Bot(command_prefix='.', self_bot=True)
logger = getLogger('main')

@bot.event
async def on_ready():
	if bot.user: logger.info(f'successful!\nrunning as {bot.user.global_name} (@{bot.user.name})')

async def main():
	for filename in os.listdir('./commands'):
		if filename.endswith('.py') and not filename.startswith('__'):
			extension = f'commands.{filename[:-3]}'
			try:
				await bot.load_extension(extension)
				logger.info(f'[+] module loaded: {extension}')
			except Exception as e: logger.warning(f'[-] module not loaded {extension}: {e}')

	await bot.start(TOKEN)

if __name__ == '__main__': asyncio.run(main())
