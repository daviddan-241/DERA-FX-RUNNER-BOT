"""Token reports (/top /kols /dev /full) + BUY/SELL execution on the report
keyboard + free-report gating + paywall."""
import asyncio

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
import reports
import solana
import texts
import trade_core
from utils import ensure_wallet

router = Router()


# ------------------------------------------------------------------ gating
async def _allowed(user_id: int) -> bool:
    """True if user has an active subscription or free reports left."""
    if await db.has_active(user_id):
        return True
    user = await db.get_user(user_id)
    if user and (user["free_used"] or 0) < config.FREE_REPORTS:
        await db.bump_free(user_id)
        return True
    return False


async def _paywall(msg):
    await msg.answer(texts.paywall(), reply_markup=kb.paywall_kb())


def _clean_ca(raw: str):
    return raw.strip().split()[0].strip("@").strip()


# ------------------------------------------------------------------ commands
@router.message(Command("top"))
async def cmd_top(message: Message, command: CommandObject):
    await _run_report(message, "TOP", (command.args or "").strip())


@router.message(Command("kols"))
async def cmd_kols(message: Message, command: CommandObject):
    await _run_report(message, "KOLS", (command.args or "").strip())


@router.message(Command("dev"))
async def cmd_dev(message: Message, command: CommandObject):
    await _run_report(message, "DEV", (command.args or "").strip())


@router.message(Command("full"))
async def cmd_full(message: Message, command: CommandObject):
    await _run_report(message, "FULL", (command.args or "").strip())


async def _run_report(message: Message, kind: str, args: str):
    ca = _clean_ca(args or "")
    if not ca:
        await message.answer(
            f"Please send the contract address.\nUsage: /{kind.lower()} <contract_address>\n"
            f"Format example:\n/{kind.lower()} 9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump")
        return
    if not await _allowed(message.from_user.id):
        await _paywall(message)
        return
    await message.answer(texts.report_running(kind))
    rep = await asyncio.to_thread(reports.build_report, ca)
    if not rep or (not rep["holders"] and not rep["price"] and not rep["liquidity_usd"]):
        await message.answer(texts.no_report_data(ca))
        return
    if kind == "KOLS":
        text = reports.format_kols(rep)
    elif kind == "DEV":
        text = reports.format_dev(rep)
    elif kind == "FULL":
        text = reports.format_full(rep)
    else:
        text = reports.format_top(rep)
    await message.answer(text, reply_markup=kb.report_kb(ca),
                         link_preview_options={"is_disabled": True})
    links_kb = kb.report_links_kb(ca, rep.get("dex_url", ""))
    await message.answer("🔗 Quick links:", reply_markup=links_kb)


# ------------------------------------------------------------------ refresh report
@router.callback_query(F.data.startswith("rep|"))
async def cb_report_refresh(query: CallbackQuery):
    await query.answer()
    ca = query.data.split("|", 1)[1]
    await query.message.answer(texts.report_running("TOP"))
    rep = await asyncio.to_thread(reports.build_report, ca)
    if not rep:
        await query.message.answer(texts.no_report_data(ca))
        return
    await query.message.answer(
        reports.format_top(rep), reply_markup=kb.report_kb(ca),
        link_preview_options={"is_disabled": True})


# ------------------------------------------------------------------ BUY / SELL (real swaps)
async def _slip(user_id: int) -> int:
    user = await db.get_user(user_id)
    slip = (user or {}).get("default_slippage") or 10
    return int(float(slip) * 100)


@router.callback_query(F.data.startswith("buy|"))
async def cb_buy(query: CallbackQuery):
    _, amt_sol, mint = query.data.split("|", 2)
    await _do_buy(query, float(amt_sol), mint)


@router.callback_query(F.data.startswith("buydef|"))
async def cb_buydef(query: CallbackQuery):
    mint = query.data.split("|", 1)[1]
    user = await db.get_user(query.from_user.id)
    amt_sol = (user or {}).get("default_buy") or 0.1
    await _do_buy(query, float(amt_sol), mint)


async def _do_buy(query: CallbackQuery, amt_sol: float, mint: str):
    await query.answer(f"🟢 Buying {amt_sol:g} SOL…")
    res = await trade_core.do_buy(query.from_user.id, mint, amt_sol,
                                  await _slip(query.from_user.id))
    if not res["ok"]:
        if res["err"] == "no_wallet":
            await ensure_wallet(query.message, query.from_user.id)
        elif res["err"] == "insufficient":
            await query.message.answer(
                texts.not_enough_balance(res["need"], res["addr"]),
                reply_markup=kb.back_to_wallet())
        else:
            await query.message.answer(texts.swap_fail(res["err"]))
        return
    got = f"{res['out_ui']:g}" if res["out_ui"] else "tokens"
    await query.message.answer(texts.swap_done(got, res["sig"], res["sym"]))


@router.callback_query(F.data.startswith("sell|"))
async def cb_sell(query: CallbackQuery):
    _, pct, mint = query.data.split("|", 2)
    await _do_sell(query, float(pct), mint)


@router.callback_query(F.data.startswith("selldef|"))
async def cb_selldef(query: CallbackQuery):
    mint = query.data.split("|", 1)[1]
    user = await db.get_user(query.from_user.id)
    pct = (user or {}).get("default_sell") or 25
    await _do_sell(query, float(pct), mint)


@router.callback_query(F.data.startswith("psell|"))
async def cb_psell(query: CallbackQuery):
    _, pct, mint = query.data.split("|", 2)
    await _do_sell(query, float(pct), mint)


async def _do_sell(query: CallbackQuery, pct: float, mint: str):
    await query.answer(f"🔴 Selling {pct:g}%…")
    res = await trade_core.do_sell_pct(query.from_user.id, mint, pct,
                                       await _slip(query.from_user.id))
    if not res["ok"]:
        if res["err"] == "no_wallet":
            await ensure_wallet(query.message, query.from_user.id)
        elif res["err"] == "empty_balance":
            await query.message.answer(texts.empty_balance(res.get("sym") or mint[:6].upper()))
        else:
            await query.message.answer(texts.swap_fail(res["err"]))
        return
    got = f"{res['out_sol']:g} SOL" if res["out_sol"] else "SOL"
    await query.message.answer(texts.swap_done(got, res["sig"], "SOL"))
