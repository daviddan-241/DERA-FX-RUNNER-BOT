# 💎 DERA FX — Runner Bot (Upgraded)

A word-for-word, button-for-button upgrade of **@runner_sol_bot** — Solana
analytics **+ a real trading bot** with a real subscription business on top.

| Feature | Original | This version |
|---|---|---|
| Reports | First 3 free, then 0.1 SOL/wk / 0.3 SOL/mo / 3 SOL lifetime | **First 3 free (kept)**, then 4 membership tiers |
| Membership | 3 flat plans | 🌱 Newbie 1 SOL · 🔰 Beginner 2 SOL · ⭐ Pro Trader 4 SOL · 💎 Elite Trader 8 SOL (prices & durations in `.env`) |
| Insider | — | **🚀 JOIN INSIDER button** right under the plans (its own price/duration, e.g. 5 SOL/30 days) — pays for the private channel |
| Channels | — | Extra paid channels in `.env`, each with own price & duration |
| Payments | Manual "Check payment" button | **Real on-chain TX verification** (amount, recipient, status, recency, no double-spend) + `/importwallet` |
| Wallet | Per-user trading wallet | Same panel + **💼 POSITIONS with live PnL** |
| Trading | BUY/SELL buttons | **Real Jupiter swaps** + **⏳ LIMIT ORDERS** that auto-execute when price hits |
| Expiry | — | **DM reminders** 48/24/6/1 h before expiry + expiry DM with Renew button + owner alerts |
| Referrals | 50% back | Same, withdrawable |

---

## 1. Local setup

```bash
cd runner-sol-bot
pip install -r requirements.txt
cp .env.example .env
nano .env              # BOT_TOKEN, OWNER_ID, prices, insider, channels…
python bot.py
```

- **BOT_TOKEN** — from @BotFather
- **OWNER_ID** — your numeric Telegram ID (from @userinfobot)
- **RPC_URL** — public works for testing; Helius/QuickNode recommended for production

## 2. Import the payment wallet

The bot verifies payments against the wallet that receives them:

- `/importwallet <PRIVATE_KEY>` in the bot DM — accepts base58 key or the
  `[46, 207, …]` 64-number array (Phantom/Backpack export format), **or**
- `TREASURY_PRIVATE_KEY=...` in `.env`

Check with `/wallet`. Payments are real on-chain SOL transfers: the bot scans
the treasury's latest transactions for a matching amount, verifies it's
finalized/recent/not-already-used, then activates the subscription and DMs the
channel invite link.

## 3. Trading (real)

- **Reports** `/top` `/kols` `/dev` `/full` — real DEXScreener + on-chain data
  with real BUY/SELL buttons underneath.
- **BUY/SELL** execute actual swaps through **Jupiter** from the user's
  auto-created wallet (BUY 0.1/0.5/1 SOL or default, SELL 25/50/100%).
- **💼 POSITIONS** — every bot buy is tracked: entry price, live price,
  value and PnL %, with one-tap 25/50/100% sells.
- **⏳ LIMIT ORDERS** — `/limit`: pick a token, BUY or SELL, target USD price
  and amount. The bot checks prices every minute and executes the swap
  automatically when your target hits, then DMs you. Retries
  `LIMIT_MAX_ATTEMPTS` times, then cancels and notifies you.
- **Holdings / withdraw** — real SPL balances; real token & SOL withdrawals.
- **Export wallet** — private key bytes + inline, same as the original.

## 4. Subscriptions & the INSIDER channel

- The **PAY menu** lists the 4 plans, and at the bottom a big
  **🚀 JOIN INSIDER — X SOL** button (price/duration from `.env`:
  `INSIDER_PRICE`, `INSIDER_DAYS`, `INSIDER_CHANNEL_ID`).
- `CHANNEL_PASSES` in `.env` adds more paid channels
  (`Name|channel_id|price|days`, days=0 → lifetime).
- The **bot must be admin** of every sold channel. On verified payment it
  creates a 1-person invite link and DMs it (`CHANNEL_ACCESS_METHOD=invite`),
  or approves the join request (`approve`). Links are revoked on expiry.
- 3 free trial reports kept: `FREE_REPORTS=3`, then the exact original
  paywall message ("🚫 3/3 FREE reports were used! …").
- **DM reminders** before expiry (`REMIND_BEFORE_HOURS=48,24,6,1`) with Renew
  buttons, expiry DMs, owner payment alerts with Solscan links, referral
  credit DMs.

## 5. Admin commands (owner only)

`/admin` · `/importwallet` · `/wallet` · `/stats` · `/verify <id> <plan|pass>`
· `/revoke <id>` · `/extend <id> <days>` · `/check <tx_sig>` · `/broadcast <text>`

## 6. Deploy on Render (free)

1. Push this repo to GitHub (see below).
2. Render → **New + → Blueprint** → pick the repo → Render reads `render.yaml`
   and creates a free **Background Worker** (workers don't sleep like free
   web services do).
3. Set the secrets in the worker's Environment tab:
   `BOT_TOKEN`, `OWNER_ID`, `TREASURY_PRIVATE_KEY`, `INSIDER_CHANNEL_ID`,
   `CHANNEL_PASSES`, `SUPPORT_LINK`.
4. Deploy → the worker runs `python bot.py` 24/7.
   (Free tier: 750 instance-hours/month — one bot = ~720 h, fits.)

You can also create the worker manually: *New → Background Worker*, runtime
Python, build `pip install -r requirements.txt`, start `python bot.py`.

## 7. Push to GitHub

```bash
cd runner-sol-bot
git init
git add .
git commit -m "DERA FX Runner Bot"
git branch -M main
git remote add origin https://github.com/daviddan-241/DERA-FX-RUNNER-BOT.git
git push -u origin main
```

**Important:** `runner.db` (users/private keys) and `.env` (secrets) are
git-ignored — never commit them.

## 8. Prices — change anytime in `.env`

```env
NEWBIE_PRICE=1      NEWBIE_DAYS=30
BEGINNER_PRICE=2    BEGINNER_DAYS=30
PRO_PRICE=4         PRO_DAYS=30
ELITE_PRICE=8       ELITE_DAYS=60
INSIDER_PRICE=5     INSIDER_DAYS=30
CHANNEL_PASSES=VIP Signals|-1001234567890|5|30
```

Restart after changing. No code edits needed.
