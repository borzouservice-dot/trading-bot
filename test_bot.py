import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot

load_dotenv(".env")

async def main():
    bot = Bot(os.getenv("BOT_TOKEN"))
    me = await bot.get_me()
    print(me.username)

asyncio.run(main())
