"""Shared async helpers: treasury, owner notify, channel access, time formatting."""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

import config
import db
import texts


def fmt_ts(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=ZoneInfo(config.TZ))
    return dt.strftime("%d %b %Y, %H:%M")


def now() -> int:
    return int(time.time())


async def get_treasury_secret() -> str:
    stored = await db.get_setting("treasury_pk", "")
    return stored or config.TREASURY_PRIVATE_KEY


async def notify_owner(bot: Bot, text: str):
    if not config.OWNER_ID:
        return
    try:
        await bot.send_message(config.OWNER_ID, text)
    except Exception as e:
        print("owner notify failed:", e)


async def grant_channel(bot: Bot, channel_id: str, user_id: int) -> str | None:
    """Grant access to a private channel. Returns invite link (invite method)
    or None. Requires the bot to be admin of the channel."""
    if not channel_id:
        return None
    try:
        if config.CHANNEL_ACCESS_METHOD == "approve":
            await bot.approve_chat_join_request(chat_id=channel_id, user_id=user_id)
            return None
        invite = await bot.create_chat_invite_link(
            chat_id=channel_id, member_limit=1, expire_date=now() + 172800
        )
        return invite.invite_link
    except TelegramBadRequest as e:
        await notify_owner(bot, texts.owner_channel_error(channel_id, e.message or str(e)))
        return None
    except Exception as e:
        await notify_owner(bot, texts.owner_channel_error(channel_id, str(e)))
        return None


async def revoke_channel(bot: Bot, channel_id: str, invite_link: str):
    if not channel_id or not invite_link:
        return
    try:
        await bot.revoke_chat_invite_link(chat_id=channel_id, invite_link=invite_link)
    except Exception:
        pass


def user_line(user: dict) -> str:
    uname = f"@{user['username']}" if user.get("username") else user.get("first_name") or "?"
    return f"{uname} (id {user['id']})"
