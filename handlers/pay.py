"""Payment & subscriptions: membership plans, channel passes, real on-chain
verification (send TX or auto-check), access granting, referral credits."""
import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
import solana
import texts
from utils import (effective_channel_id, fmt_ts, get_treasury_address,
                   grant_channel, notify_owner, now, parse_tx_ref, user_line)

router = Router()


class PayStates(StatesGroup):
    tx_input = State()


# ------------------------------------------------------------------ menus
@router.message(Command("pay"))
async def cmd_pay(message: Message):
    await message.answer(texts.membership_header(), reply_markup=kb.pay_menu())


@router.callback_query(F.data == "pay")
async def cb_pay(query: CallbackQuery):
    await query.answer()
    await query.message.answer(texts.membership_header(), reply_markup=kb.pay_menu())


async def _detail_text(item, kind: str) -> str:
    """Plan/pass detail + the 'Unlock … deposit to the address below' block
    (exactly like the original bot's unlock screen)."""
    if kind == "plan":
        label = f"{item['emoji']} {item['name']}"
        detail = texts.plan_detail(item)
    else:
        label = item['name'] if item["key"] != "insider" else config.INSIDER_NAME
        detail = texts.pass_detail(item)
    addr = await get_treasury_address()
    if addr:
        detail += "\n\n" + texts.unlock_text(label, item["price"], item["days"], addr)
    else:
        detail += "\n\n⚠️ Payment address is not set up yet — contact /support."
    return detail


@router.callback_query(F.data.startswith("plan|"))
async def cb_plan(query: CallbackQuery):
    await query.answer()
    key = query.data.split("|", 1)[1]
    plan = config.get_plan(key)
    if not plan:
        return
    addr = await get_treasury_address()
    await query.message.answer(await _detail_text(plan, "plan"),
                               reply_markup=kb.plan_detail_kb(key, addr))


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
    addr = await get_treasury_address()
    await query.message.answer(await _detail_text(c, "pass"),
                               reply_markup=kb.pass_detail_kb(key, addr))


@router.callback_query(F.data.startswith("renew|"))
async def cb_renew(query: CallbackQuery):
    await query.answer()
    _, kind, key = query.data.split("|", 2)
    addr = await get_treasury_address()
    if kind == "plan":
        plan = config.get_plan(key)
        if plan:
            await query.message.answer(await _detail_text(plan, "plan"),
                                       reply_markup=kb.plan_detail_kb(key, addr))
    else:
        c = config.get_pass(key)
        if c:
            await query.message.answer(await _detail_text(c, "pass"),
                                       reply_markup=kb.pass_detail_kb(key, addr))


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


def _item_of(kind: str, key: str):
    return config.get_plan(key) if kind == "plan" else config.get_pass(key)


# ------------------------------------------------------------------ payment: send TX (real verification)
@router.callback_query(F.data.startswith("tx|"))
async def cb_tx_payment(query: CallbackQuery, state: FSMContext):
    await query.answer()
    _, kind, key = query.data.split("|", 2)
    item = _item_of(kind, key)
    if not item:
        return
    address = await get_treasury_address()
    if not address:
        await query.message.answer(texts.no_treasury())
        return
    await state.set_state(PayStates.tx_input)
    await state.update_data(tx_kind=kind, tx_key=key)
    label = f"{item['emoji']} {item['name']}" if kind == "plan" else item['name']
    await query.message.answer(texts.ask_tx(label, item["price"], address))


@router.message(PayStates.tx_input)
async def got_tx(message: Message, state: FSMContext):
    data = await state.get_data()
    kind, key = data.get("tx_kind"), data.get("tx_key")
    await state.clear()
    item = _item_of(kind, key)
    if not item:
        return

    address = await get_treasury_address()
    if not address:
        await message.answer(texts.no_treasury())
        return

    sig = parse_tx_ref(message.text or "")
    if not sig:
        await message.answer(
            "❌ That doesn't look like a transaction.\n\n"
            "Send the transaction signature or a Solscan link, e.g.:\n"
            "https://solscan.io/tx/5KzKz…9Xw",
            reply_markup=kb.check_pay_only(kind, key, item["price"]))
        return

    await message.answer(texts.checking())
    used = await db.payment_sigs()
    if sig in used:
        await message.answer(
            "⚠️ That transaction was already used for another payment.\n"
            "If this is a mistake, contact us via /support with your tx signature.")
        return

    res = await asyncio.to_thread(solana.verify_single_tx, sig, address)
    min_ts = now() - config.TX_WINDOW_HOURS * 3600
    if not res or not res.get("ok"):
        await message.answer(
            texts.payment_failed(item["price"]),
            reply_markup=kb.check_pay_only(kind, key, item["price"]))
        return
    if (res.get("ts") or 0) and res["ts"] < min_ts:
        await message.answer(
            "⛔ That transaction is too old to verify.\n"
            f"Payments must be within the last {config.TX_WINDOW_HOURS} hours.",
            reply_markup=kb.check_pay_only(kind, key, item["price"]))
        return
    lamports = res.get("lamports") or 0
    if lamports < solana.sol_to_lam(item["price"]):
        await message.answer(
            texts.payment_failed(item["price"]),
            reply_markup=kb.check_pay_only(kind, key, item["price"]))
        return

    await _finalize_payment(message.bot, message, message.from_user.id,
                            kind, item, sig, lamports, res.get("payer", ""))


# ------------------------------------------------------------------ payment: auto-check (scan fallback)
@router.callback_query(F.data.startswith("check|"))
async def cb_check_payment(query: CallbackQuery):
    await query.answer()
    _, kind, key = query.data.split("|", 2)
    item = _item_of(kind, key)
    if not item:
        return

    address = await get_treasury_address()
    if not address:
        await query.message.answer(texts.no_treasury())
        return

    await query.message.answer(texts.checking())
    used = await db.payment_sigs()
    result = await asyncio.to_thread(_verify_payment, address, item["price"], used)
    if not result:
        await query.message.answer(
            texts.payment_failed(item["price"]),
            reply_markup=kb.check_pay_only(kind, key, item["price"]))
        return

    sig, lamports, payer = result
    await _finalize_payment(query.message.bot, query.message, query.from_user.id,
                            kind, item, sig, lamports, payer)


async def _finalize_payment(bot, msg: Message, user_id: int, kind: str, item: dict,
                            sig: str, lamports: int, payer: str):
    """Shared: record payment, grant channel, create subscription, notify."""
    label = f"{item['emoji']} {item['name']}" if kind == "plan" else f"📢 {item['name']}"

    ok = await db.register_payment(sig, user_id, label, lamports, payer)
    if not ok:
        await msg.answer(
            "⚠️ That transaction was already used for another payment.\n"
            "If this is a mistake, contact us via /support with your tx signature.")
        return

    channels = []
    cid = await effective_channel_id(item)
    if cid:
        channels = [cid]
    links = []
    for cid in channels:
        link = await grant_channel(bot, cid, user_id)
        if link:
            links.append(link)
    links_block = "\n".join(f"🔗 {l}" for l in links)

    if kind == "pass" and not links:
        await notify_owner(
            bot,
            f"⚠️ {label} was paid ({lamports / 1e9:g} SOL) but NO channel is "
            f"configured for it yet — no invite link was generated.\n"
            f"👤 {user_line(await db.get_user(user_id))}\n"
            f"Use /setchannel {item['key']} then send the link manually.")

    sub = await db.add_subscription(
        user_id=user_id, kind=kind, item_key=item["key"], label=label,
        lamports=lamports, days=item["days"], tx_sig=sig, payer=payer,
        invite_link="\n".join(links),
        channel_id=channels[0] if channels else "",
    )
    end_str = "∞ (Lifetime 🚀)" if not sub["end_ts"] else fmt_ts(sub["end_ts"])
    await msg.answer(
        texts.payment_success(label, lamports / 1e9, item["days"], end_str, links_block),
        reply_markup=kb.main_menu(),
        link_preview_options={"is_disabled": True},
    )

    user = await db.get_user(user_id)
    await notify_owner(
        bot,
        texts.owner_payment_alert(user_line(user), label, lamports / 1e9, sig),
        reply_markup=kb.owner_tx_kb(sig))

    if user and user.get("referred_by"):
        credit = int(lamports * config.REF_PERCENT / 100)
        if credit > 0:
            await db.add_credits(user["referred_by"], credit)
            try:
                await bot.send_message(
                    user["referred_by"],
                    texts.ref_credit_alert(credit / 1e9, user_line(user)))
            except Exception:
                pass


def _verify_payment(address: str, price_sol: float, used_sigs: set):
    """Blocking: scan the treasury's real on-chain history for the payment."""
    required = solana.sol_to_lam(price_sol)
    min_ts = now() - config.TX_WINDOW_HOURS * 3600
    return solana.scan_treasury_for_payment(address, required, used_sigs, min_ts)
