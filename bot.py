"""
Private Alpha Bot — run:  python bot.py
Also starts a tiny HTTP health server (PORT env) so Render's web-service
health check and UptimeRobot pings get 200 OK — keeps the free tier awake.
"""
import asyncio
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
from handlers import admin, common, pay, reports, trading
from scheduler import scheduler_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("runner")


def start_health_server():
    """Minimal HTTP server answering 200 OK on every path."""
    port = int(os.environ.get("PORT", "10000"))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"OK"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    try:
        srv = HTTPServer(("0.0.0.0", port), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        log.info("Health server listening on port %s", port)
    except Exception as e:
        log.warning("Could not start health server: %s", e)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(common.router)
    dp.include_router(pay.router)
    dp.include_router(trading.router)
    dp.include_router(reports.router)
    dp.include_router(admin.router)
    return dp


async def main():
    if not config.BOT_TOKEN or "PASTE" in config.BOT_TOKEN.upper():
        raise SystemExit(
            "❌ BOT_TOKEN is not set (or still the placeholder).\n"
            "Open .env, put your real token from @BotFather, and restart."
        )
    if not config.OWNER_ID:
        print("⚠️ OWNER_ID is 0 — admin commands and admin DMs are disabled "
              "until you set your Telegram ID in .env.")
    await db.init_db()

    bot = Bot(token=config.BOT_TOKEN)
    dp = build_dispatcher()

    # real command list in the "/" menu (like the original bot)
    from aiogram.types import BotCommand
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Start the bot"),
            BotCommand(command="top", description="Get a SMART holders report"),
            BotCommand(command="kols", description="Get KOLs report for this CA"),
            BotCommand(command="dev", description="Get a dev report (bought, sold, holding)"),
            BotCommand(command="full", description="Get a full report: dev, KOLs & holders"),
            BotCommand(command="pay", description="Payment and plan upgrade"),
            BotCommand(command="trading", description="Trading settings (buy, sell, slippage, wallet)"),
            BotCommand(command="holdings", description="Tokens on your balance"),
            BotCommand(command="positions", description="Your open positions with live PnL"),
            BotCommand(command="limit", description="Set a limit order (auto-executes)"),
            BotCommand(command="withdraw", description="Withdraw tokens from your trading wallet"),
            BotCommand(command="ref", description="Generate ref link, manage referrals"),
            BotCommand(command="help", description="Docs and guide"),
            BotCommand(command="support", description="Contact us for support / feedback"),
        ])
    except Exception as e:
        log.warning("set_my_commands failed: %s", e)

    # health endpoint (Render web service + UptimeRobot keep-alive)
    start_health_server()

    # background job: expiry reminders + limit orders
    asyncio.create_task(scheduler_loop(bot))

    log.info("Private Alpha Bot started 🚀")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
