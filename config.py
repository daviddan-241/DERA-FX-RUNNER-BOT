"""
Runner Bot (upgraded clone) — configuration.
Everything business-related (prices, durations, channels) is editable in .env
so you never have to touch the code to change a price.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------- basics
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
_owner_raw = (os.getenv("OWNER_ID", "0") or "0").strip()
try:
    OWNER_ID = int(_owner_raw or 0)
except ValueError:
    raise SystemExit(
        "❌ OWNER_ID in .env is not a number.\n"
        "Put YOUR Telegram ID there (get it from @userinfobot).\n"
        "Example: OWNER_ID=123456789"
    ) from None
SUPPORT_LINK = os.getenv("SUPPORT_LINK", "https://t.me/runnerbotsupport")
DOCS_URL = os.getenv("DOCS_URL", "https://runner-bot.gitbook.io/runner-bot-docs")
TZ = os.getenv("TZ", "Africa/Lagos")
AD_LINE = os.getenv("AD_LINE", "Trade, Earn & Launch on Vyper")

# ---------------------------------------------------------------- access / gating
FREE_REPORTS = int(os.getenv("FREE_REPORTS", "3"))
REF_PERCENT = float(os.getenv("REF_PERCENT", "50"))

# ---------------------------------------------------------------- payments
# The bot's receiving wallet (imported by the owner via /importwallet or env).
# Accepts: base58 private key, [64-byte array], OR a 12/24-word seed phrase.
TREASURY_PRIVATE_KEY = os.getenv("TREASURY_PRIVATE_KEY", "").strip()
# ALTERNATIVE: just a public receiving ADDRESS (no key). Payments are still
# verified on-chain against it. You need the private key (above or
# /importwallet) only for referral-credit payouts.
TREASURY_ADDRESS = os.getenv("TREASURY_ADDRESS", "").strip()
TX_WINDOW_HOURS = int(os.getenv("TX_WINDOW_HOURS", "48"))      # how old a tx may be
MIN_CONFIRM_LEVEL = os.getenv("MIN_CONFIRM_LEVEL", "finalized")

# ---------------------------------------------------------------- public channel
# Free public channel — shown as a button in the main menu + welcome message.
PUBLIC_CHANNEL_LINK = os.getenv("PUBLIC_CHANNEL_LINK", "").strip()

# ---------------------------------------------------------------- user wallets
# MASTER SEED: when set, the bot generates a UNIQUE deterministic wallet for
# every user (sha256(seed | user_id)) when they tap "GENERATE WALLET".
# Leave empty to generate random wallets per user instead.
WALLET_SEED = os.getenv("WALLET_SEED", "").strip()
# Guard: a leftover placeholder would silently derive every user wallet from
# garbage — treat it as unset and warn loudly instead.
if "PASTE" in WALLET_SEED.upper() or "EXAMPLE" in WALLET_SEED.upper() or WALLET_SEED.lower().startswith("your_"):
    print("⚠️ WALLET_SEED looks like a placeholder — using RANDOM wallets per user. "
          "Set the real 12/24-word seed in .env / Render env to enable derived wallets.")
    WALLET_SEED = ""

# ---------------------------------------------------------------- subscriptions
REMIND_BEFORE_HOURS = [
    int(x) for x in os.getenv("REMIND_BEFORE_HOURS", "48,24,6,1").split(",") if x.strip()
]

# ---------------------------------------------------------------- channels
# How the bot grants channel access: "invite" (bot must be admin in channel,
# generates 1-person invite links) or "approve" (channel must have join requests ON).
CHANNEL_ACCESS_METHOD = os.getenv("CHANNEL_ACCESS_METHOD", "invite").strip().lower()

# ---------------------------------------------------------------- AI (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# =====================================================================
#  MEMBERSHIP PLANS  (prices & durations from .env — text is fixed)
# =====================================================================

def _f(name, default):
    return float(os.getenv(name, str(default)))


def _i(name, default):
    return int(os.getenv(name, str(default)))


# ---------------------------------------------------------------------
#  📅 VIP ACCESS — unlock unlimited reports + trading after 3 free trials
#  reports after the 3 free trials (like the original bot's month plan).
# ---------------------------------------------------------------------
BOT_MONTH_NAME = os.getenv("BOT_MONTH_NAME", "VIP Access").strip()
BOT_MONTH_PRICE = float(os.getenv("BOT_MONTH_PRICE", "5"))
BOT_MONTH_DAYS = int(os.getenv("BOT_MONTH_DAYS", "30"))

PLANS = [
    {
        "key": "access",
        "emoji": "📅",
        "name": BOT_MONTH_NAME,
        "price": BOT_MONTH_PRICE,
        "days": BOT_MONTH_DAYS,
        "channel_id": "",
        "desc": (
            "Unlimited reports for the bot.\n\n"
            "• No free-trial limit\n"
            "• Full /top /kols /dev /full access\n"
            "• Real trading side included\n"
            "• Renews monthly"
        ),
    },
    {
        "key": "newbie",
        "emoji": "🌱",
        "name": "Newbie",
        "price": _f("NEWBIE_PRICE", 1),
        "days": _i("NEWBIE_DAYS", 30),
        "channel_id": os.getenv("NEWBIE_CHANNEL_ID", "").strip(),
        "desc": (
            "For beginners with little or no trading experience.\n\n"
            "• Basic alpha calls\n"
            "• Learn memecoin trading\n"
            "• Suitable for first-time members"
        ),
    },
    {
        "key": "beginner",
        "emoji": "🔰",
        "name": "Beginner",
        "price": _f("BEGINNER_PRICE", 2),
        "days": _i("BEGINNER_DAYS", 30),
        "channel_id": os.getenv("BEGINNER_CHANNEL_ID", "").strip(),
        "desc": (
            "Everything in Newbie.\n\n"
            "• More frequent trade signals\n"
            "• Market updates\n"
            "• Basic trading guidance"
        ),
    },
    {
        "key": "pro",
        "emoji": "⭐",
        "name": "Pro Trader",
        "price": _f("PRO_PRICE", 4),
        "days": _i("PRO_DAYS", 30),
        "channel_id": os.getenv("PRO_CHANNEL_ID", "").strip(),
        "desc": (
            "Everything in Beginner.\n\n"
            "• Priority alpha calls\n"
            "• Advanced trade setups\n"
            "• Faster alerts\n"
            "• Higher-quality analysis"
        ),
    },
    {
        "key": "elite",
        "emoji": "💎",
        "name": "Elite Trader",
        "price": _f("ELITE_PRICE", 8),
        "days": _i("ELITE_DAYS", 60),
        "channel_id": os.getenv("ELITE_CHANNEL_ID", "").strip(),
        "desc": (
            "Full premium access.\n\n"
            "• Earliest alerts\n"
            "• Full signal access\n"
            "• Premium market analysis\n"
            "• Highest-priority support\n"
            "• Exclusive content"
        ),
    },
]


def get_plan(key: str):
    for p in PLANS:
        if p["key"] == key:
            return p
    return None


# =====================================================================
#  CHANNEL SUBSCRIPTIONS (the "channel side")
#  .env format:  CHANNEL_PASSES="Name|channel_id|price|days;Name2|id2|price2|days2"
#  days=0  ->  lifetime
# =====================================================================

def parse_passes(raw: str):
    passes = []
    if not raw:
        return passes
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        bits = [b.strip() for b in part.split("|")]
        if len(bits) != 4:
            continue
        name, cid, price, days = bits
        try:
            price = float(price)
            days = int(days)
        except ValueError:
            continue
        # sanitize + cap name for callback data safety (Telegram limit: 64 bytes)
        safe = "".join(ch for ch in name if ch.isalnum() or ch in " _-")[:24]
        passes.append({
            "key": safe or "channel",
            "name": name,
            "channel_id": cid,
            "price": price,
            "days": days,
        })
    return passes


CHANNEL_PASSES = parse_passes(os.getenv("CHANNEL_PASSES", ""))

# Max attempts to execute a limit order before cancelling it.
LIMIT_MAX_ATTEMPTS = int(os.getenv("LIMIT_MAX_ATTEMPTS", "3"))


def get_pass(key: str):
    for p in CHANNEL_PASSES:
        if p["key"] == key:
            return p
    return None


# =====================================================================
#  Optional: tag top-holder wallets with KOL names for the /kols report
#  .env:  KOL_TAGS="Wallet=Name,Wallet2=Name2"
# =====================================================================

def parse_kols(raw: str):
    out = {}
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            w, n = part.split("=", 1)
            out[w.strip()] = n.strip()
    return out


KOL_TAGS = parse_kols(os.getenv("KOL_TAGS", ""))
