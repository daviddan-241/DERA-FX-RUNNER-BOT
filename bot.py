"""
Runner Bot — upgraded clone.
Run:  python bot.py
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
from handlers import admin, common, pay, reports, trading
from scheduler import scheduler_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("runner")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(common.router)
    dp.include_router(pay.router)
    dp.include_router(trading.router)
    dp.include_router(reports.router)
    dp.include_router(admin.router)
    return dp


async def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")
    await db.init_db()

    bot = Bot(token=config.BOT_TOKEN)
    dp = build_dispatcher()

    # background job: expiry reminders + renewals DM
    asyncio.create_task(scheduler_loop(bot))

    log.info("INSIDER PROFITS Bot started 🚀")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
