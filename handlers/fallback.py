"""LAST-resort handler — this router MUST be included AFTER every other router
(see bot.py). If the FSM state was lost (e.g. Render restarts mid-import), a
pasted seed phrase / private key still completes the wallet import, as long as
the user is actually waiting for one (DB flag) or has no wallet yet.

It never steals random messages: only private, non-command text that truly
validates as a wallet secret is treated as an import. Everything else is
ignored, and nothing here crashes on non-text messages.
"""
import asyncio
import logging

from aiogram import Router
from aiogram.types import Message

import db
import solana
from handlers.trading import complete_import

router = Router()
log = logging.getLogger("runner")


def _looks_like_secret(text: str) -> bool:
    """Cheap shape check before doing real crypto validation."""
    stripped = text.strip()
    # 12/24-word seed phrase (letters only, no punctuation/digits)
    if 12 <= len(stripped.split()) <= 24 and all(w.isalpha() for w in stripped.split()):
        return True
    # JSON byte array [46, 207, ...]
    if len(stripped) >= 32 and stripped.startswith("[") and stripped.endswith("]"):
        return True
    # base58 private key (~87-88 chars, alnum, no spaces)
    if 80 <= len(stripped) <= 128 and " " not in stripped and stripped.isalnum():
        return True
    return False


@router.message()
async def import_fallback(message: Message):
    # Private chat text only; never touch commands or photos/stickers
    if not message.text or message.chat.type != "private" or message.text.startswith("/"):
        return
    raw = message.text.strip()
    if len(raw) > 3000:
        return

    user_id = message.from_user.id
    flag = await db.get_setting(f"awaiting_import:{user_id}", "0")
    user = await db.get_user(user_id)
    has_wallet = bool(user and user.get("wallet_pub"))
    # Only treat as import when the user is waiting for one or has no wallet yet
    if flag != "1" and has_wallet:
        return  # random message from a user who already has a wallet

    # pull the real key out of noisy pastes; if nothing seed-shaped was found
    # and the user isn't mid-import, ignore the message entirely
    text = solana.extract_secret(raw)
    if text == raw and flag != "1" and not _looks_like_secret(raw):
        return

    try:
        addr = await asyncio.to_thread(solana.validate_secret, text)
    except Exception as e:
        # Seed-shaped text that isn't a valid wallet — tell them, keep waiting
        await message.answer(
            f"❌ Invalid wallet:\n{e}\n\nSend a 12/24-word seed phrase, "
            "a base58 private key, or a [64-byte array]:")
        return

    try:
        await complete_import(message, text, addr)
    except Exception as e:
        log.error(f"import_fallback failed for user {user_id}: {e}", exc_info=True)
        try:
            await message.answer(
                "❌ Wallet import error — please try again or use /importwallet.",
                parse_mode="HTML")
        except Exception:
            pass
