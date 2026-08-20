"""Owner/admin commands: import wallet, wallet, stats, verify, revoke, extend,
check tx, broadcast."""
import asyncio

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

import config
import db
import solana
from utils import fmt_ts, get_treasury_secret, now

router = Router()


def _owner(message: Message) -> bool:
    return config.OWNER_ID and message.from_user.id == config.OWNER_ID


class AdminStates(StatesGroup):
    import_wallet = State()
    broadcast = State()


# ------------------------------------------------------------------ panel
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not _owner(message):
        return
    secret = await get_treasury_secret()
    addr = solana.treasury_address_from(secret) if secret else "NOT SET"
    users = await db.count_users()
    revenue, pays = await db.total_revenue_lamports()
    subs = await db.active_subs_all()
    active = len([s for s in subs if not s["end_ts"] or s["end_ts"] > now()])
    await message.answer(
        "🛠 ADMIN PANEL\n\n"
        f"👥 Users: {users}\n"
        f"💎 Active subscriptions: {active}\n"
        f"💰 Payments: {pays}\n"
        f"💵 Revenue: {solana.lam_to_sol(revenue):g} SOL\n\n"
        f"👛 Treasury: <code>{addr}</code>\n\n"
        "Commands:\n"
        "/importwallet <base58_key OR [64-byte array]> — set the receiving wallet\n"
        "/wallet — treasury address + balance\n"
        "/stats — full stats\n"
        "/verify <user_id> <newbie|beginner|pro|elite> — manual grant (no tx needed)\n"
        "/verify <user_id> <pass name> — manual grant of a channel pass\n"
        "/revoke <user_id> — end a user's subscriptions\n"
        "/extend <user_id> <days> — extend active subscriptions\n"
        "/check <tx_signature> — inspect a single transaction\n"
        "/broadcast <text> — DM all users\n"
        "/importwallet — without args asks for the key in the next message"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not _owner(message):
        return
    users = await db.count_users()
    revenue, pays = await db.total_revenue_lamports()
    subs = await db.active_subs_all()
    active = [s for s in subs if not s["end_ts"] or s["end_ts"] > now()]
    plans_n = len([s for s in active if s["kind"] == "plan"])
    passes_n = len([s for s in active if s["kind"] == "pass"])
    await message.answer(
        "📈 BOT STATS\n\n"
        f"👥 Users: {users}\n"
        f"💎 Active plan subs: {plans_n}\n"
        f"📢 Active channel passes: {passes_n}\n"
        f"💰 Total payments: {pays}\n"
        f"💵 Revenue: {solana.lam_to_sol(revenue):g} SOL"
    )


# ------------------------------------------------------------------ wallet import / treasury
@router.message(Command("importwallet"))
async def cmd_importwallet(message: Message, command: CommandObject, state: FSMContext):
    if not _owner(message):
        return
    args = (command.args or "").strip()
    if not args:
        await state.set_state(AdminStates.import_wallet)
        await message.answer(
            "🔐 Send the wallet PRIVATE KEY now.\n\n"
            "Accepted formats (same as the bot's export):\n"
            "• base58 string (Phantom/Backpack format)\n"
            "• JSON byte array [46, 207, ...] (64 numbers)\n\n"
            "This wallet receives ALL subscription payments.")
        return
    await _do_import(message, args, state)


@router.message(AdminStates.import_wallet)
async def got_wallet_key(message: Message, state: FSMContext):
    await _do_import(message, message.text, state)


async def _do_import(message: Message, secret: str, state: FSMContext):
    try:
        addr = solana.validate_secret(secret)
    except Exception as e:
        await message.answer(f"❌ Invalid private key: {e}")
        return
    await db.set_setting("treasury_pk", secret.strip())
    await state.clear()
    await message.answer(
        f"✅ Wallet imported!\n\n👛 Treasury address:\n<code>{addr}</code>\n\n"
        "All subscription payments must be sent to this address — the bot "
        "verifies them on-chain in real time.")


@router.message(Command("wallet"))
async def cmd_wallet(message: Message):
    if not _owner(message):
        return
    secret = await get_treasury_secret()
    if not secret:
        await message.answer("⚠️ Treasury wallet is NOT set.\nUse /importwallet or set TREASURY_PRIVATE_KEY in .env")
        return
    addr = solana.treasury_address_from(secret)
    balance = await asyncio.to_thread(solana.sol_balance, addr)
    await message.answer(
        f"👛 Treasury wallet:\n<code>{addr}</code>\n\n"
        f"💰 Balance: {solana.lam_to_sol(balance):g} SOL")


# ------------------------------------------------------------------ manual verify / revoke / extend
@router.message(Command("verify"))
async def cmd_verify(message: Message, command: CommandObject):
    if not _owner(message):
        return
    parts = (command.args or "").strip().split()
    if len(parts) < 2:
        await message.answer("Usage: /verify <user_id> <plan_key|pass name>")
        return
    try:
        user_id = int(parts[0])
    except ValueError:
        await message.answer("❌ Bad user id.")
        return
    key = " ".join(parts[1:]).lower()
    plan = config.get_plan(key)
    if plan:
        kind, item, label = "plan", plan, f"{plan['emoji']} {plan['name']}"
    else:
        c = next((p for p in config.CHANNEL_PASSES if p["name"].lower() == key), None)
        if not c:
            await message.answer(f"❌ Unknown plan/pass: {key}")
            return
        kind, item, label = "pass", c, f"📢 {c['name']}"
    await db.register_payment(f"manual_{message.from_user.id}_{now()}", user_id, label,
                              solana.sol_to_lam(item["price"]), "manual")
    sub = await db.add_subscription(
        user_id=user_id, kind=kind, item_key=item["key"], label=label,
        lamports=solana.sol_to_lam(item["price"]), days=item["days"],
        tx_sig="manual", payer="manual")
    end = "Lifetime" if not sub["end_ts"] else fmt_ts(sub["end_ts"])
    await message.answer(f"✅ Manually granted {label} to user {user_id} until {end}.")
    try:
        await message.bot.send_message(
            user_id,
            f"🎉 Your {label} access was activated by the team!\n⏳ Until: {end}")
    except Exception:
        pass


@router.message(Command("revoke"))
async def cmd_revoke(message: Message, command: CommandObject):
    if not _owner(message):
        return
    args = (command.args or "").strip()
    if not args.isdigit():
        await message.answer("Usage: /revoke <user_id>")
        return
    user_id = int(args)
    for s in await db.get_active_subs(user_id):
        await db.set_sub_status(s["id"], "revoked")
    await message.answer(f"✅ Revoked subscriptions for user {user_id}.")


@router.message(Command("extend"))
async def cmd_extend(message: Message, command: CommandObject):
    if not _owner(message):
        return
    parts = (command.args or "").strip().split()
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Usage: /extend <user_id> <days>")
        return
    user_id, days = int(parts[0]), int(parts[1])
    n = 0
    for s in await db.get_active_subs(user_id):
        if s["end_ts"]:
            new_end = (max(s["end_ts"], now())) + days * 86400
            await db.update_sub_end(s["id"], new_end)
            n += 1
    await message.answer(f"✅ Extended {n} subscription(s) of user {user_id} by {days} days.")


# ------------------------------------------------------------------ tx check
@router.message(Command("check"))
async def cmd_check(message: Message, command: CommandObject):
    if not _owner(message):
        return
    sig = (command.args or "").strip()
    if not sig:
        await message.answer("Usage: /check <tx_signature>")
        return
    secret = await get_treasury_secret()
    if not secret:
        await message.answer("⚠️ Treasury not set.")
        return
    addr = solana.treasury_address_from(secret)
    res = await asyncio.to_thread(solana.verify_single_tx, sig, addr)
    if res is None:
        await message.answer("❌ Transaction not found.")
        return
    await message.answer(
        f"🔎 TX: <code>{sig}</code>\n\n"
        f"OK: {'✅' if res['ok'] else '❌'}\n"
        f"Received: {solana.lam_to_sol(res.get('lamports', 0)):g} SOL\n"
        f"Payer: {res.get('payer')}\n"
        f"Time: {fmt_ts(res.get('ts') or 0)}")


# ------------------------------------------------------------------ broadcast
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject, state: FSMContext):
    if not _owner(message):
        return
    args = (command.args or "").strip()
    if not args:
        await state.set_state(AdminStates.broadcast)
        await message.answer("📣 Send the text to broadcast to all users:")
        return
    await _broadcast(message, args, state)


@router.message(AdminStates.broadcast)
async def got_broadcast(message: Message, state: FSMContext):
    await _broadcast(message, message.html_text or message.text, state)


async def _broadcast(message: Message, text: str, state: FSMContext):
    await state.clear()
    users = await db.all_users()
    ok, fail = 0, 0
    for u in users:
        try:
            await message.bot.send_message(u["id"], text)
            ok += 1
        except Exception:
            fail += 1
    await message.answer(f"📣 Broadcast done: {ok} sent, {fail} failed.")
