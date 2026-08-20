"""
Background loop (every 60 s):
  1. DM reminders + expiry notices for subscriptions (with Renew buttons)
  2. Execute open limit orders when their target price is hit (real swaps)
"""
import asyncio

from aiogram import Bot

import config
import db
import keyboards as kb
import reports
import texts
import trade_core
from utils import fmt_ts, notify_owner, now, revoke_channel


async def scheduler_loop(bot: Bot):
    while True:
        try:
            await check_subscriptions(bot)
        except Exception as e:
            print("scheduler subs error:", e)
        try:
            await check_limit_orders(bot)
        except Exception as e:
            print("scheduler limits error:", e)
        await asyncio.sleep(60)


async def check_limit_orders(bot: Bot):
    """Watch open limit orders and execute real swaps when price crosses."""
    orders = await db.open_limit_orders()
    if not orders:
        return

    # fetch prices once per unique mint
    prices = {}
    for mint in {o["mint"] for o in orders}:
        try:
            prices[mint] = await asyncio.to_thread(reports.get_price_usd, mint)
        except Exception:
            prices[mint] = None

    for o in orders:
        price = prices.get(o["mint"])
        if price is None:
            continue  # feed unavailable; try again next cycle
        side, target = o["side"], o["target_price"]
        hit = (side == "buy" and price <= target) or (side == "sell" and price >= target)
        if not hit:
            continue

        sym = o["symbol"] or o["mint"][:8]
        try:
            if side == "buy":
                res = await trade_core.do_buy(o["user_id"], o["mint"], o["amount"],
                                              o["slippage_bps"])
            else:
                res = await trade_core.do_sell_pct(o["user_id"], o["mint"], o["amount"],
                                                   o["slippage_bps"])
        except Exception as e:
            res = {"ok": False, "err": str(e)[:200]}

        if res.get("ok"):
            await db.mark_limit(o["id"], "executed", res.get("sig", ""))
            try:
                await bot.send_message(
                    o["user_id"],
                    texts.limit_executed(sym, side, target, res.get("sig", "")))
            except Exception:
                pass
            continue

        attempts = await db.bump_limit_attempt(o["id"])
        if attempts >= config.LIMIT_MAX_ATTEMPTS:
            await db.mark_limit(o["id"], "failed", res.get("err", "")[:120])
            try:
                await bot.send_message(
                    o["user_id"], texts.limit_failed(sym, side, res.get("err", "")))
            except Exception:
                pass


async def check_subscriptions(bot: Bot):
    subs = await db.active_subs_all()
    for s in subs:
        end = s["end_ts"]
        user_id = s["user_id"]
        label = s["label"]
        item_ref = f"{s['kind']}|{s['item_key']}"

        # expired?
        if end and end <= now():
            await db.set_sub_status(s["id"], "expired")
            await revoke_channel(bot, s["channel_id"], s["invite_link"])
            try:
                await bot.send_message(
                    user_id,
                    texts.expired_text(label, fmt_ts(end)),
                    reply_markup=kb.renew_kb(s["kind"], s["item_key"],
                                             sol_float(s["price_lamports"]), label),
                )
            except Exception:
                pass
            await notify_owner(
                bot,
                f"🔴 Subscription expired: {label} — user id {user_id}.",
            )
            continue

        if not end:
            continue  # lifetime

        # reminders
        for h in sorted(config.REMIND_BEFORE_HOURS):
            threshold = end - h * 3600
            if now() >= threshold:
                if await db.mark_notified(s["id"], h):
                    hours_left = max((end - now()) / 3600, 0)
                    try:
                        await bot.send_message(
                            user_id,
                            texts.reminder_text(label, hours_left, fmt_ts(end)),
                            reply_markup=kb.renew_kb(s["kind"], s["item_key"],
                                                     sol_float(s["price_lamports"]), label),
                        )
                    except Exception:
                        pass


def sol_float(lamports: int) -> float:
    return lamports / 1e9
