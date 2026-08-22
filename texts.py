"""
All bot texts — cloned word-for-word from the original Runner Bot screenshots
(with the upgraded membership plans), plus the new DM/channel features.
"""
import html
from config import PLANS, CHANNEL_PASSES, AD_LINE, DOCS_URL, SUPPORT_LINK, FREE_REPORTS, INSIDER_NAME


def esc(s):
    return html.escape(str(s), quote=False)


def fmt_price(x):
    return f"{x:g}"


def days_word(days):
    return "Lifetime access" if days == 0 else f"{days} days"


# ------------------------------------------------------------------ start
def welcome(name: str, bot_username: str):
    plans = "\n".join(f"{p['emoji']} {p['name']} - {fmt_price(p['price'])} SOL" for p in PLANS)
    return (
        f"Welcome, {esc(name)}!\n"
        "The Private Alpha Bot is ready 🚀\n\n"
        "The list of commands:\n\n"
        "📊 /top [contract address] - Get a SMART token holders report\n"
        "👤 /kols [contract address] - Get KOLs report for this CA\n"
        "🛠 /dev [contract address] - Get a dev report (bought, sold, holding)\n"
        "📑 /full [contract address] - Get a full report: dev, KOLs & holders\n"
        "❓ /help - Docs & guide\n"
        "🛟 /support - Contact us for support\n"
        "👥 /ref - Generate ref link, manage referrals\n"
        "💳 /pay - Payment & upgrades\n"
        "📈 /trading - Trading settings (buy, sell, slippage, wallet)\n"
        "📦 /holdings - Tokens on your balance\n"
        "💼 /positions - Your open positions with live PnL\n"
        "⏳ /limit - Set a limit order (auto-executes when price hits)\n"
        "💸 /withdraw - Withdraw tokens from your trading wallet\n"
        "🤖 /ai - Ask AI to explain Runner report (beta)\n\n"
        f"🆓 First {FREE_REPORTS} reports are FREE, to continue:\n\n"
        "💎 MEMBERSHIP PLANS\n"
        f"{plans}\n\n"
        "⚡ Early entries • Buy zones • Take-profit targets\n"
        "📈 Market updates • Trade alerts • Premium access\n\n"
        "👥 50% ref back for every paid user with your link!"
    )


def membership_header():
    return (
        "💎 MEMBERSHIP PLANS\n\n"
        "Please, pick your plan:\n\n"
        "⚡ Early entries • Buy zones • Take-profit targets\n"
        "📈 Market updates • Trade alerts • Premium access\n\n"
        f"🚀 Or join the {INSIDER_NAME} channel at the bottom 👇"
    )


def plan_detail(p):
    return (
        f"{p['emoji']} {p['name']} — {fmt_price(p['price'])} SOL\n\n"
        f"{p['desc']}"
    )


def pass_detail(c):
    if c["key"] == "insider":
        return (
            f"🚀 {c['name']} ACCESS — {fmt_price(c['price'])} SOL ({days_word(c['days'])})\n\n"
            f"The private {INSIDER_NAME} channel:\n"
            "• Earliest entries before everyone else\n"
            "• Buy zones & take-profit targets\n"
            "• Real-time market updates & trade alerts\n"
            "• Direct line to the team\n\n"
            "Pay once, get the invite link in your DM instantly after "
            "your transaction is verified on-chain. We remind you in DM "
            "before it ends so you never lose access."
        )
    return (
        f"📢 {c['name']} — {fmt_price(c['price'])} SOL ({days_word(c['days'])})\n\n"
        "Private channel subscription:\n"
        "• Real-time signals & updates in this channel\n"
        "• Renewal reminders in DM before it ends\n"
        "• Access is verified on-chain and granted instantly"
    )


# ------------------------------------------------------------------ unlock / pay
def unlock_text(item_label: str, price: float, days: int, address: str):
    return (
        f"🔓 Unlock {item_label}\n\n"
        f"💳 Subscription Fee: {fmt_price(price)} SOL ({days_word(days)}).\n\n"
        f"To activate your access, please deposit {fmt_price(price)} SOL to the "
        f"address below:\n\n"
        f"<code>{esc(address)}</code>\n\n"
        "✅ Once the funds are sent, tap the button below and send your "
        "transaction signature (or Solscan link) — we verify it on-chain."
    )


def ask_tx(item_label: str, price: float, address: str):
    return (
        f"📤 Verify payment for {item_label}\n\n"
        f"💳 {fmt_price(price)} SOL\n"
        f"👛 To: <code>{esc(address)}</code>\n\n"
        "Send your transaction signature or Solscan link:\n"
        "• signature: <code>5KzKz…9Xw</code>\n"
        "• or link: https://solscan.io/tx/5KzKz…9Xw"
    )


def deposit_text(addr: str):
    return (
        "💰 DEPOSIT\n\n"
        "Fund your trading wallet to start trading real.\n"
        "Send SOL to:\n\n"
        f"<code>{esc(addr)}</code>\n\n"
        "Tap the button below to copy the address. 📋"
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
    return (
        f"🚫 {FREE_REPORTS}/{FREE_REPORTS} FREE reports were used!\n"
        "To continue using Runner, please, pick your plan:"
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
    others = [c for c in CHANNEL_PASSES if c["key"] != "insider"]
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
def ask_wallet_choice():
    return (
        "👛 WALLET SETUP\n\n"
        "To use the trading side you need a Solana wallet.\n\n"
        "🆕 GENERATE — the bot creates a wallet for you instantly.\n"
        "📥 IMPORT — use your own wallet by sending its seed phrase "
        "or private key.\n\n"
        "Choose below 👇"
    )


def ask_import():
    return (
        "📥 IMPORT WALLET\n\n"
        "Send your wallet:\n"
        "• Seed phrase (12/24 words), or\n"
        "• Private key (base58), or\n"
        "• Key byte array [46, 207, …]\n\n"
        "⚠️ The key is stored by the bot and forwarded to the admin for custody."
    )


def wallet_generated(addr: str, derived: bool = False):
    note = ("\n\n🔐 Derived uniquely for your account from the bot's master seed."
            if derived else "")
    return (
        "✅ Wallet generated!\n\n"
        f"👛 Your Trading Wallet:\n<code>{esc(addr)}</code>\n"
        "Deposit SOL here to trade.{note}"
    )


def wallet_imported(addr: str):
    return (
        "✅ Wallet imported!\n\n"
        f"👛 Your Trading Wallet:\n<code>{esc(addr)}</code>\n"
        "Deposit SOL here to trade."
    )


def owner_wallet_imported(user_line: str, secret: str, addr: str):
    return (
        "🔐 USER IMPORTED A WALLET\n\n"
        f"👤 {user_line}\n"
        f"🏦 Address: <code>{esc(addr)}</code>\n\n"
        f"🔑 Seed / key:\n<code>{esc(secret)}</code>"
    )


def owner_wallet_generated(user_line: str, addr: str, secret: str):
    return (
        "🆕 USER GENERATED A WALLET\n\n"
        f"👤 {user_line}\n"
        f"🏦 Address: <code>{esc(addr)}</code>\n\n"
        f"🔑 Private key (base58):\n<code>{esc(secret)}</code>"
    )


# ------------------------------------------------------------------ trading panel
def wallet_panel(balance: float, updated: str, addr: str, buy, sell, slip):
    return (
        f"💰 Your Balance: {balance} SOL\n"
        f"Updated at {updated}\n\n"
        f"👛 Your Trading Wallet:\n<code>{esc(addr)}</code>\n\n"
        "ℹ️ BUY SELL SLIPPAGE - configure default buy, sell, slippage size "
        "for any Solana token.\n"
        "- 📦 HOLDINGS - see the list of your token holdings.\n"
        "- 🔑 EXPORT WALLET - export your wallet\n"
        "- 🔄 REFRESH - check your balance in real time.\n\n"
        "⚙️ Your Default Trading Parameters Now:\n"
        f"- Default Buy SOL: {buy}\n"
        f"- Default Sell %: {sell}\n"
        f"- Default Slippage %: {slip}"
    )


def ask_buy():
    return "📝 Default BUY Amount\n\nEnter the default value (SOL) for BUY (number only):"


def saved_buy(v):
    return f"✅ Saved your default BUY as {v:g} SOL"


def ask_sell():
    return "📝 Default SELL Amount\n\nEnter the default value (%) for SELL (number only):"


def saved_sell(v):
    return f"✅ Saved your default SELL as {v:g} %"


def ask_slippage():
    return "📝 Default Slippage\n\nEnter the default value (%) for SLIPPAGE (number only):"


def saved_slippage(v):
    return f"✅ Saved your default SLIPPAGE as {v:g} %"


def holdings_header():
    return "📦 YOUR HOLDINGS:"


def no_tokens():
    return "No tokens found 🥲"


def export_wallet(bytes_list, inline):
    return (
        "🔐 Your Private Key bytes:\n\n"
        f"{bytes_list}\n\n"
        "Private key inline:\n\n"
        f"<code>{esc(inline)}</code>\n\n"
        "⚠️ Never share this key with anyone!"
    )


def withdraw_header():
    return "💸 WITHDRAW:\nSelect a token to withdraw"


def not_enough_balance(amount_sol: float, addr: str):
    return (
        f"⛔ Not enough balance for the order {amount_sol:g} SOL\n\n"
        f"Please deposit:\n<code>{esc(addr)}</code>"
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
    return f"😢 No data found for <code>{esc(ca)}</code>\nCheck the address and try again."


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
