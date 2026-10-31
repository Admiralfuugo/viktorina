import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import db
import web
from config import ADMIN_IDS, BOT_TOKEN, CHANNEL_ID, PANEL_HOST, PANEL_PORT
from handlers import admin, user
from middlewares import RememberUser


async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init_db(ADMIN_IDS, CHANNEL_ID)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.update.outer_middleware(RememberUser())
    dp.include_routers(admin.router, user.router)

    web.app.state.bot = bot
    server = uvicorn.Server(uvicorn.Config(web.app, host=PANEL_HOST, port=PANEL_PORT, log_level="info"))
    logging.info("Admin panel: http://%s:%s", PANEL_HOST, PANEL_PORT)
    await asyncio.gather(dp.start_polling(bot, handle_signals=False), server.serve())


if __name__ == "__main__":
    asyncio.run(main())
