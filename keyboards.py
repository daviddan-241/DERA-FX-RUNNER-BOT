"""
All inline keyboards — cloned button-for-button from the original bot,
plus the membership / insider / channel / trading upgrades.
"""
from aiogram.types import CopyTextButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import PLANS, CHANNEL_PASSES, get_plan, get_pass
import config


def _b(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


# ---------------------------------------------------------------- main
def main_menu():
    b = InlineKeyboardBuilder()
    b.row(_b("📈 TRADING", "wp"), _b("💳 PAY", "pay"))
    if config.PUBLIC_CHANNEL_LINK:
        b.row(InlineKeyboardButton(text="📣 PUBLIC CHANNEL", url=config.PUBLIC_CHANNEL_LINK))
    return b.as_markup()


def paywall_kb():
    """Shown when the 3 free trial reports are used — single monthly access
    first, then the membership tiers (like the original bot's paywall)."""
    b = InlineKeyboardBuilder()
    for p in PLANS[:1]:   # 📅 Monthly Access
        b.row(_b(f"{p['emoji']} {p['name']} - {p['price']:g} SOL ({p['days']} days)", f"plan|{p['key']}"))
    for p in PLANS[1:]:   # membership tiers
        b.row(_b(f"{p['emoji']} {p['name']} - {p['price']:g} SOL", f"plan|{p['key']}"))
    b.row(_b("🔙 Menu", "menu"))
    return b.as_markup()


# ---------------------------------------------------------------- pay
def pay_menu():
    b = InlineKeyboardBuilder()
    for p in PLANS[:1]:   # 📅 Monthly Access (bot access)
        b.row(_b(f"{p['emoji']} {p['name']} - {p['price']:g} SOL ({p['days']} days)", f"plan|{p['key']}"))
    for p in PLANS[1:]:   # membership tiers
        b.row(_b(f"{p['emoji']} {p['name']} - {p['price']:g} SOL", f"plan|{p['key']}"))
    if CHANNEL_PASSES:
        b.row(_b("📢 Channel Subscriptions", "channels"))
    b.row(_b("📊 My Subscription", "mysub"), _b("🔙 Back", "menu"))
    return b.as_markup()


def plan_detail_kb(plan_key: str, addr: str = ""):
    p = get_plan(plan_key)
    if not p:
        return pay_menu()
    b = InlineKeyboardBuilder()
    b.row(_b("✅ I'VE PAID — SEND TX", f"tx|plan|{p['key']}"))
    b.row(_b("🔙 Back to plans", "pay"))
    return b.as_markup()


def channels_kb():
    b = InlineKeyboardBuilder()
    for c in CHANNEL_PASSES:
        b.row(_b(f"{c['name']} - {c['price']:g} SOL", f"pass|{c['key']}"))
    b.row(_b("🔙 Back", "pay"))
    return b.as_markup()


def pass_detail_kb(pass_key: str, addr: str = ""):
    c = get_pass(pass_key)
    if not c:
        return channels_kb()
    b = InlineKeyboardBuilder()
    b.row(_b("✅ I'VE PAID — SEND TX", f"tx|pass|{c['key']}"))
    b.row(_b("🔙 Back", "pay"))
    return b.as_markup()


def check_pay_only(kind: str, key: str, price: float):
    b = InlineKeyboardBuilder()
    b.row(_b("✅ I'VE PAID — SEND TX", f"tx|{kind}|{key}"))
    b.row(_b("🔙 Back", "pay"))
    return b.as_markup()


def renew_kb(kind: str, key: str, price: float, label: str):
    b = InlineKeyboardBuilder()
    b.row(_b(f"💳 Renew {label} — {price:g} SOL", f"renew|{kind}|{key}"))
    b.row(_b("📊 My Subscription", "mysub"), _b("🔙 Menu", "menu"))
    return b.as_markup()


def mysub_kb(plan_key=None, pass_keys=None):
    b = InlineKeyboardBuilder()
    if plan_key:
        p = get_plan(plan_key)
        if p:
            b.row(_b(f"💳 Renew {p['emoji']} {p['name']} — {p['price']:g} SOL", f"renew|plan|{p['key']}"))
    for k in (pass_keys or []):
        c = get_pass(k)
        if c:
            b.row(_b(f"💳 Renew {c['name']} — {c['price']:g} SOL", f"renew|pass|{c['key']}"))
    b.row(_b("💳 PAY", "pay"), _b("🔙 Menu", "menu"))
    return b.as_markup()


# ---------------------------------------------------------------- trading
def wallet_panel_kb():
    b = InlineKeyboardBuilder()
    b.row(_b("🟢 BUY", "setbuy"), _b("🔴 SELL", "setsell"), _b("⚙️ SLIPPAGE", "setslip"))
    b.row(_b("📦 HOLDINGS", "holdings"), _b("💼 POSITIONS", "positions"))
    b.row(_b("⏳ LIMIT ORDERS", "limits"), _b("🔑 EXPORT WALLET", "export"))
    b.row(_b("💰 DEPOSIT", "deposit"), _b("📥 IMPORT WALLET", "wimp"))
    b.row(_b("🔄 REFRESH", "refresh"), _b("💸 WITHDRAW", "withdraw"))
    b.row(_b("🔙 Menu", "menu"))
    return b.as_markup()


def deposit_kb(addr: str = ""):
    b = InlineKeyboardBuilder()
    b.row(_b("🔙 Back", "wp"))
    return b.as_markup()


def holdings_kb():
    b = InlineKeyboardBuilder()
    b.row(_b("🔄 REFRESH", "holdings"))
    b.row(_b("🔙 Back", "wp"))
    return b.as_markup()


def positions_kb(positions):
    b = InlineKeyboardBuilder()
    for p in positions[:8]:
        sym = (p["symbol"] or p["mint"][:6])[:14]
        b.row(
            _b(f"🔴 {sym} 25%", f"psell|25|{p['mint']}"),
            _b(f"🔴 {sym} 50%", f"psell|50|{p['mint']}"),
            _b(f"🔴 {sym} 100%", f"psell|100|{p['mint']}"),
        )
    b.row(_b("🔄 REFRESH", "positions"), _b("⏳ LIMIT ORDERS", "limits"))
    b.row(_b("🔙 Back", "wp"))
    return b.as_markup()


def limits_kb(orders):
    b = InlineKeyboardBuilder()
    for o in orders[:8]:
        sym = (o["symbol"] or o["mint"][:6])[:14]
        side = "🟢 BUY" if o["side"] == "buy" else "🔴 SELL"
        b.row(_b(f"❌ {sym} {side} @ ${o['target_price']:g}", f"lcancel|{o['id']}"))
    b.row(_b("➕ NEW LIMIT ORDER", "newlimit"))
    b.row(_b("🔄 REFRESH", "limits"), _b("🔙 Back", "wp"))
    return b.as_markup()


def limit_side_kb():
    b = InlineKeyboardBuilder()
    b.row(_b("🟢 BUY limit", "ls_buy"), _b("🔴 SELL limit", "ls_sell"))
    return b.as_markup()


def limit_confirm_kb():
    b = InlineKeyboardBuilder()
    b.row(_b("✅ Confirm", "lconfirm"), _b("❌ Cancel", "lcancel"))
    return b.as_markup()


def export_kb(key: str = "", seed: str = "", bytes_str: str = ""):
    b = InlineKeyboardBuilder()
    b.row(_b("🔙 Back", "wp"))
    return b.as_markup()


# ---------------------------------------------------------------- copy helpers
def copy_only_kb(text: str, label: str = "📋 COPY"):
    b = InlineKeyboardBuilder()
    if len(text) <= 256:
        b.row(InlineKeyboardButton(text=label, copy_text=CopyTextButton(text=text)))
    return b.as_markup()


def wallet_done_kb(addr: str, key: str):
    b = InlineKeyboardBuilder()
    b.row(_b("🔙 Back", "wp"))
    return b.as_markup()


def admin_copy_kb(addr: str, secret: str):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📋 COPY ADDRESS", copy_text=CopyTextButton(text=addr)))
    if secret and len(secret) <= 256:
        b.row(InlineKeyboardButton(text="📋 COPY KEY / SEED", copy_text=CopyTextButton(text=secret)))
    return b.as_markup()


def owner_tx_kb(sig: str):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔗 SOLSCAN", url=f"https://solscan.io/tx/{sig}"))
    if len(sig) <= 256:
        b.row(InlineKeyboardButton(text="📋 COPY TX", copy_text=CopyTextButton(text=sig)))
    return b.as_markup()


def withdraw_kb(tokens=None):
    b = InlineKeyboardBuilder()
    b.row(_b("💠 SOL", "wd|SOL"))
    for t in (tokens or [])[:8]:
        label = t.get("symbol") or t["mint"][:8]
        b.row(_b(f"{label} ({t['ui']:g})", f"wd|{t['mint']}"))
    b.row(_b("🔄 REFRESH", "withdraw"))
    b.row(_b("🔙 Back", "wp"))
    return b.as_markup()


def back_to_wallet():
    b = InlineKeyboardBuilder()
    b.row(_b("🔙 Back", "wp"))
    return b.as_markup()


# ---------------------------------------------------------------- wallet setup
def wallet_setup_kb():
    b = InlineKeyboardBuilder()
    b.row(_b("🆕 GENERATE WALLET", "wgen"))
    b.row(_b("📥 IMPORT WALLET", "wimp"))
    return b.as_markup()


# ---------------------------------------------------------------- reports
def report_kb(mint: str):
    b = InlineKeyboardBuilder()
    b.row(_b("🟢 BUY", f"buydef|{mint}"), _b("0.1 SOL", f"buy|0.1|{mint}"),
          _b("0.5 SOL", f"buy|0.5|{mint}"), _b("1 SOL", f"buy|1|{mint}"))
    b.row(_b("🔴 SELL", f"selldef|{mint}"), _b("25%", f"sell|25|{mint}"),
          _b("50%", f"sell|50|{mint}"), _b("100%", f"sell|100|{mint}"))
    b.row(_b("🔄 REFRESH", f"rep|{mint}"), _b("📈 TRADING", "wp"))
    b.row(_b("🔙 Menu", "menu"))
    return b.as_markup()


def report_links_kb(mint: str, dexscreener_url: str = ""):
    b = InlineKeyboardBuilder()
    if dexscreener_url:
        b.add(InlineKeyboardButton(text="DEX", url=dexscreener_url))
    b.add(InlineKeyboardButton(text="AXM", url=f"https://axiom.trade/token/{mint}?chain=solana"))
    b.add(InlineKeyboardButton(text="TRO", url=f"https://t.me/ttm_solana_bot?start={mint}"))
    b.add(InlineKeyboardButton(text="PDR", url=f"https://pump.fun/coin/{mint}"))
    b.add(InlineKeyboardButton(text="PHO", url=f"https://photon-sol.tinyastro.io/en/lp/{mint}"))
    b.add(InlineKeyboardButton(text="NEO", url=f"https://neo.bullx.io/terminal?chainId=1399811149&address={mint}"))
    b.add(InlineKeyboardButton(text="GMGN", url=f"https://gmgn.ai/sol/token/{mint}"))
    b.add(InlineKeyboardButton(text="BLZ", url=f"https://birdeye.so/token/{mint}?chain=solana"))
    b.adjust(8)
    return b.as_markup()
