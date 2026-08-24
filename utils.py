"""Shared async helpers: treasury, owner notify, channel access, time formatting."""
import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

import config
import db
import solana
import texts


def fmt_ts(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=ZoneInfo(config.TZ))
    return dt.strftime("%d %b %Y, %H:%M")


def now() -> int:
    return int(time.time())


async def get_treasury_secret() -> str:
    stored = await db.get_setting("treasury_pk", "")
    return stored or config.TREASURY_PRIVATE_KEY


async def get_treasury_address() -> str:
    """The address payments are verified against. Order:
    1) /setaddress (DB)  2) TREASURY_ADDRESS in .env  3) private key derived.
    NO private key needed — a public receiving address is enough."""
    import solana
    stored = await db.get_setting("treasury_addr", "")
    if stored and "PASTE" not in stored.upper():
        return stored.strip()
    if config.TREASURY_ADDRESS and "PASTE" not in config.TREASURY_ADDRESS.upper():
        return config.TREASURY_ADDRESS.strip()
    secret = await get_treasury_secret()
    if secret:
        try:
            return solana.treasury_address_from(secret)
        except Exception:
            pass
    return ""


async def effective_channel_id(item: dict) -> str:
    """Channel id for a plan/pass: .env value first, then /setchannel (DB).
    Invite links in .env are ignored (bots can't resolve them) — use
    /setchannel with a forwarded message instead."""
    cid = (item.get("channel_id") or "").strip()
    if cid and not cid.startswith("http"):
        return cid
    stored = await db.get_setting(f"ch_{item['key']}", "")
    return (stored or "").strip()


async def notify_owner(bot: Bot, text: str, reply_markup=None):
    if not config.OWNER_ID:
        return
    try:
        await bot.send_message(config.OWNER_ID, text, reply_markup=reply_markup)
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


def parse_tx_ref(text: str):
    """Extract a transaction signature from raw text, a Solscan/Explorer/Solana.fm
    link, or a t.me link. Returns the signature or None."""
    import re
    text = (text or "").strip()
    # bare signature
    m = re.search(r"[1-9A-HJ-NP-Za-km-z]{87,88}", text)
    if m:
        return m.group(0)
    return None


async def ensure_wallet(msg, user_id: int):
    """Return the user with their trading wallet. Does NOT auto-generate.
    If no wallet exists and msg is provided, prompts GENERATE / IMPORT.
    Keeps /importwallet real. Never crashes the /start flow."""
    import logging, keyboards as kb
    log = logging.getLogger("runner")
    try:
        user = await db.ensure_user(user_id)
    except Exception as e:
        log.error(f"ensure_wallet: db.ensure_user failed for {user_id}: {e}")
        if msg:
            try:
                await msg.answer(
                    "❌ Could not load your account. Please try /start again.",
                    parse_mode="HTML", reply_markup=kb.wallet_setup_kb())
            except Exception:
                pass
        return None
    if user.get("wallet_pub"):
        return user
    # No wallet — prompt setup if a message handle is available
    if msg:
        try:
            await msg.answer(
                texts.ask_wallet_choice(),
                parse_mode="HTML", reply_markup=kb.wallet_setup_kb())
        except Exception as e:
            log.warning(f"ensure_wallet: failed to send wallet setup prompt: {e}")
    return None
