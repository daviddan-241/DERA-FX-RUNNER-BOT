"""Common handlers: /start, /help, /support, /ref, /ai, menu callbacks."""
import asyncio

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
import solana
import texts
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from solana import lam_to_sol

router = Router()


class AiStates(StatesGroup):
    ai_ca = State()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    args = command.args or ""
    referred_by = None
    if args.startswith("ref_"):
        code = args[4:].strip()
        ref_user = await db.get_user_by_ref(code)
        if ref_user and ref_user["id"] != message.from_user.id:
            referred_by = ref_user["id"]

    user = await db.ensure_user(
        message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        referred_by=referred_by,
    )

    # auto-create the trading wallet on first start (like the original bot)
    if not user.get("wallet_pub"):
        kp = await asyncio.to_thread(solana.new_keypair)
        await db.set_wallet(user["id"], str(kp), str(kp.pubkey()))

    bot_info = await message.bot.me()
    await message.answer(
        texts.welcome(message.from_user.first_name or "trader", bot_info.username),
        reply_markup=kb.main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(texts.help_text(), reply_markup=kb.main_menu())


@router.message(Command("support"))
async def cmd_support(message: Message):
    await message.answer(texts.support_text())


@router.message(Command("ref"))
async def cmd_ref(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        return
    refs = await db.count_refs(user["id"])
    credits = lam_to_sol(user.get("credits_lamports") or 0)
    bot_info = await message.bot.me()
    await message.answer(texts.ref_text(bot_info.username, user["ref_code"], refs, credits))


@router.message(Command("ai"))
async def cmd_ai(message: Message, state: FSMContext):
    await state.set_state(AiStates.ai_ca)
    await message.answer(texts.ask_ai())


@router.message(AiStates.ai_ca)
async def got_ai_ca(message: Message, state: FSMContext):
    ca = message.text.strip().split()[0].strip("@").strip()
    await state.clear()
    import config
    if not config.OPENAI_API_KEY:
        await message.answer(texts.ai_unavailable())
        return
    import reports
    await message.answer("🤖 Thinking…")
    rep = await asyncio.to_thread(reports.build_report, ca)
    if not rep:
        await message.answer(texts.no_report_data(ca))
        return
    summary = (
        f"Token {rep['name']} ({rep['symbol']}), price ${rep['price']}, "
        f"liquidity {rep['liquidity_usd']}, 24h volume {rep['volume_usd']}, "
        f"smart score {rep['score']}/30, top holders: "
        + "; ".join(f"{h['pct']:.1f}%" for h in rep["holders"][:5])
    )
    explanation = await asyncio.to_thread(_openai_explain, summary)
    await message.answer(texts.ai_answer(explanation))


def _openai_explain(summary: str) -> str:
    import requests
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system",
                 "content": "You explain memecoin/token reports briefly for traders. "
                            "Max 6 short lines, plain words, no markdown headers."},
                {"role": "user", "content": f"Explain this Runner report: {summary}"},
            ],
            "max_tokens": 300,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


@router.callback_query(F.data == "menu")
async def cb_menu(query: CallbackQuery):
    await query.answer()
    user = await db.get_user(query.from_user.id)
    if not user:
        return
    bot_info = await query.message.bot.me()
    await query.message.answer(
        texts.welcome(user.get("first_name") or "trader", bot_info.username),
        reply_markup=kb.main_menu(),
    )


@router.callback_query(F.data == "help")
async def cb_help(query: CallbackQuery):
    await query.answer()
    await query.message.answer(texts.help_text(), reply_markup=kb.main_menu())


@router.callback_query(F.data == "support")
async def cb_support(query: CallbackQuery):
    await query.answer()
    await query.message.answer(texts.support_text())


@router.callback_query(F.data == "back_ai")
async def cb_back_ai(query: CallbackQuery):
    await query.answer()
    await query.message.answer(texts.ask_ai())
