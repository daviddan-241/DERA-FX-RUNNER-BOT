"""
trade_core — shared REAL trade execution (Jupiter swaps + position tracking).
Used by the inline BUY/SELL buttons AND by the limit-order engine.
"""
import asyncio

import db
import reports
import solana


async def symbol_of(mint: str) -> str:
    try:
        rep = await asyncio.to_thread(reports.build_report, mint)
        return (rep or {}).get("symbol") or mint[:6].upper()
    except Exception:
        return mint[:6].upper()


async def _kp(user_id: int):
    user = await db.get_user(user_id)
    if not user or not user.get("wallet_priv"):
        return None
    try:
        return solana.keypair_from_secret(user["wallet_priv"])
    except Exception:
        return None


async def do_buy(user_id: int, mint: str, amt_sol: float, slippage_bps: int) -> dict:
    """Real market buy: SOL -> token. Returns {'ok': bool, ...}"""
    kp = await _kp(user_id)
    if not kp:
        return {"ok": False, "err": "no_wallet"}
    need = solana.sol_to_lam(amt_sol)
    balance = await asyncio.to_thread(solana.sol_balance, str(kp.pubkey()))
    if balance < need + solana.sol_to_lam(0.005):
        return {"ok": False, "err": "insufficient", "addr": str(kp.pubkey()),
                "need": amt_sol}
    try:
        quote = await asyncio.to_thread(
            solana.jupiter_quote, solana.SOL_MINT, mint, need, slippage_bps)
        sig = await asyncio.to_thread(solana.jupiter_swap, kp, quote)
    except Exception as e:
        return {"ok": False, "err": str(e)[:300]}
    out = quote.get("outAmount")
    out_ui = float(out) / 1e6 if out else None
    sym = await symbol_of(mint)
    if out_ui:
        await db.add_position_trade(user_id, mint, sym, out_ui, 6, amt_sol, sig)
    return {"ok": True, "sig": sig, "out_ui": out_ui, "sym": sym, "spent_sol": amt_sol}


async def do_sell_pct(user_id: int, mint: str, pct: float, slippage_bps: int) -> dict:
    """Real market sell: sell pct% of the user's holding of `mint` for SOL."""
    kp = await _kp(user_id)
    if not kp:
        return {"ok": False, "err": "no_wallet"}
    tokens = await asyncio.to_thread(solana.token_accounts, str(kp.pubkey()))
    tok = next((t for t in tokens if t["mint"] == mint), None)
    if not tok:
        return {"ok": False, "err": "empty_balance", "sym": await symbol_of(mint)}
    amount = int(tok["amount"] * pct / 100)
    if amount <= 0:
        return {"ok": False, "err": "empty_balance", "sym": await symbol_of(mint)}
    try:
        quote = await asyncio.to_thread(
            solana.jupiter_quote, mint, solana.SOL_MINT, amount, slippage_bps)
        sig = await asyncio.to_thread(solana.jupiter_swap, kp, quote)
    except Exception as e:
        return {"ok": False, "err": str(e)[:300]}
    out = quote.get("outAmount")
    out_sol = float(out) / 1e9 if out else None
    sym = await symbol_of(mint)
    sold_ui = tok["ui"] * pct / 100
    await db.reduce_position(user_id, mint, sold_ui)
    return {"ok": True, "sig": sig, "out_sol": out_sol, "sym": sym,
            "sold_ui": sold_ui, "decimals": tok["decimals"]}


async def position_line(user_id: int, pos: dict) -> str:
    """Live PnL line for one open position."""
    entry_sol = (pos["spent_sol"] or 0) / pos["qty"] if pos["qty"] else 0
    try:
        usd = await asyncio.to_thread(reports.get_price_usd, pos["mint"])
        sol_usd = await asyncio.to_thread(reports.get_sol_price_usd)
    except Exception:
        usd = None
        sol_usd = 0.0
    sym = pos["symbol"] or pos["mint"][:6].upper()
    if usd and sol_usd:
        cur_sol = usd / sol_usd
        value = cur_sol * pos["qty"]
        pnl = ((cur_sol - entry_sol) / entry_sol * 100) if entry_sol else 0.0
        arrow = "🟢" if pnl >= 0 else "🔴"
        return (
            f"• ${sym} ({pos['mint'][:4]}…)\n"
            f"  Qty: {pos['qty']:,.2f}\n"
            f"  Entry: {entry_sol:.8f} SOL/token\n"
            f"  Now: {cur_sol:.8f} SOL/token\n"
            f"  Value: {value:.3f} SOL\n"
            f"  PnL: {pnl:+.1f}% {arrow}"
        )
    return (
        f"• ${sym} ({pos['mint'][:4]}…)\n"
        f"  Qty: {pos['qty']:,.2f}\n"
        f"  Entry: {entry_sol:.8f} SOL/token\n"
        f"  (price feed unavailable right now)"
    )
