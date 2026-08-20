"""Payment & subscriptions: membership plans, channel passes, real on-chain
verification, access granting, DM expiry reminders data, referral credits."""
import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
import solana
import texts
from utils import (fmt_ts, get_treasury_secret, grant_channel, notify_owner, now,
                   user_line)

router = Router()


# ------------------------------------------------------------------ menus
@router.message(Command("pay"))
async def cmd_pay(message: Message):
    await message.answer(
        texts.membership_header(), reply_markup=kb.pay_menu()
    )


@router.callback_query(F.data == "pay")
async def cb_pay(query: CallbackQuery):
    await query.answer()
    await query.message.answer(texts.membership_header(), reply_markup=kb.pay_menu())


@router.callback_query(F.data.startswith("plan|"))
async def cb_plan(query: CallbackQuery):
    await query.answer()
    key = query.data.split("|", 1)[1]
    plan = config.get_plan(key)
    if not plan:
        return
    await query.message.answer(texts.plan_detail(plan), reply_markup=kb.plan_detail_kb(key))


@router.callback_query(F.data == "channels")
async def cb_channels(query: CallbackQuery):
    await query.answer()
    await query.message.answer(texts.channels_menu(), reply_markup=kb.channels_kb())


@router.callback_query(F.data.startswith("pass|"))
async def cb_pass(query: CallbackQuery):
    await query.answer()
    key = query.data.split("|", 1)[1]
    c = config.get_pass(key)
    if not c:
        return
    await query.message.answer(texts.pass_detail(c), reply_markup=kb.pass_detail_kb(key))


@router.callback_query(F.data.startswith("renew|"))
async def cb_renew(query: CallbackQuery):
    await query.answer()
    _, kind, key = query.data.split("|", 2)
    if kind == "plan":
        plan = config.get_plan(key)
        if plan:
            await query.message.answer(texts.plan_detail(plan), reply_markup=kb.plan_detail_kb(key))
    else:
        c = config.get_pass(key)
        if c:
            await query.message.answer(texts.pass_detail(c), reply_markup=kb.pass_detail_kb(key))


# ------------------------------------------------------------------ my subscription
@router.message(Command("mysub"))
async def cmd_mysub(message: Message):
    await _show_mysub(message)


@router.callback_query(F.data == "mysub")
async def cb_mysub(query: CallbackQuery):
    await query.answer()
    await _show_mysub(query.message)


async def _show_mysub(msg):
    user = await db.get_user(msg.from_user.id)
    if not user:
        return
    subs = await db.get_active_subs(user["id"])
    plan_row, pass_rows, links = None, [], []
    for s in subs:
        expired = s["end_ts"] and s["end_ts"] <= now()
        end = "Lifetime 🚀" if not s["end_ts"] else fmt_ts(s["end_ts"])
        status = "🔴 Expired" if expired else "🟢 Active"
        line = (
            f"💎 {s['label']}\n"
            f"⏳ Until: {end}\n"
            f"✅ Status: {status}"
        )
        if s["invite_link"]:
            line += f"\n🔗 Access: {s['invite_link']}"
        if s["kind"] == "plan":
            plan_row = line
        else:
            pass_rows.append(line)
    links_note = "🔗 Tap an access link above to join the private channel." \
        if any(s["invite_link"] for s in subs) else None
    await msg.answer(
        texts.my_sub_text(plan_row, pass_rows, links_note),
        reply_markup=kb.mysub_kb(
            plan_key=next((s["item_key"] for s in subs if s["kind"] == "plan"), None),
            pass_keys=[s["item_key"] for s in subs if s["kind"] == "pass"],
        ),
    )


# ------------------------------------------------------------------ unlock & check payment
@router.callback_query(F.data.startswith("check|"))
async def cb_check_payment(query: CallbackQuery):
    await query.answer()
    _, kind, key = query.data.split("|", 2)
    if kind == "plan":
        item = config.get_plan(key)
    else:
        item = config.get_pass(key)
    if not item:
        return

    secret = await get_treasury_secret()
    if not secret:
        await query.message.answer(texts.no_treasury())
        return

    await query.message.answer(texts.checking())
    used = await db.payment_sigs()
    result = await asyncio.to_thread(_verify_payment, secret, item["price"], used)
    if not result:
        await query.message.answer(
            texts.payment_failed(item["price"]),
            reply_markup=kb.check_pay_only(kind, key, item["price"]),
        )
        return

    sig, lamports, payer = result
    label = f"{item['emoji']} {item['name']}" if kind == "plan" else f"📢 {item['name']}"

    # record the payment (unique tx signature — nobody can reuse a tx)
    ok = await db.register_payment(sig, query.from_user.id, label, lamports, payer)
    if not ok:
        await query.message.answer(
            "⚠️ That transaction was already used for another payment.\n"
            "If this is a mistake, contact us via /support with your tx signature.")
        return

    # grant channel access
    channels = [item["channel_id"]] if item.get("channel_id") else []
    links = []
    for cid in channels:
        link = await grant_channel(query.message.bot, cid, query.from_user.id)
        if link:
            links.append(link)
    links_block = "\n".join(f"🔗 {l}" for l in links)

    sub = await db.add_subscription(
        user_id=query.from_user.id,
        kind=kind,
        item_key=item["key"],
        label=label,
        lamports=lamports,
        days=item["days"],
        tx_sig=sig,
        payer=payer,
        invite_link="\n".join(links),
        channel_id=channels[0] if channels else "",
    )
    end_str = "∞ (Lifetime 🚀)" if not sub["end_ts"] else fmt_ts(sub["end_ts"])
    await query.message.answer(
        texts.payment_success(label, lamports / 1e9, item["days"], end_str, links_block),
        reply_markup=kb.main_menu(),
        link_preview_options={"is_disabled": True},
    )

    # owner alert
    user = await db.get_user(query.from_user.id)
    await notify_owner(
        query.message.bot,
        texts.owner_payment_alert(user_line(user), label, lamports / 1e9, sig),
    )

    # referral credit (50% back to the referrer)
    if user and user.get("referred_by"):
        credit = int(lamports * config.REF_PERCENT / 100)
        if credit > 0:
            await db.add_credits(user["referred_by"], credit)
            try:
                await query.message.bot.send_message(
                    user["referred_by"],
                    texts.ref_credit_alert(credit / 1e9, user_line(user)),
                )
            except Exception:
                pass


def _verify_payment(secret: str, price_sol: float, used_sigs: set):
    """Blocking: scan the treasury's real on-chain history for the payment."""
    treasury = solana.treasury_address_from(secret)
    required = solana.sol_to_lam(price_sol)
    min_ts = now() - config.TX_WINDOW_HOURS * 3600
    return solana.scan_treasury_for_payment(treasury, required, used_sigs, min_ts)
