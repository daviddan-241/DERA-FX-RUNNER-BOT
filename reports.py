"""
Token reports (/top /kols /dev /full) built from real on-chain + DEXScreener data.
Blocking — call via asyncio.to_thread.
"""
import time
from datetime import datetime, timezone

import requests

import config
from solana import SOL_MINT, mint_authority, token_largest, token_supply


def _dex(mint: str) -> dict:
    """Best DEXScreener pair for a token."""
    r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=15)
    r.raise_for_status()
    pairs = (r.json() or {}).get("pairs") or []
    if not pairs:
        return {}
    return max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd") or 0))


def _jup_price(mint: str):
    try:
        r = requests.get(f"https://api.jup.ag/price/v2?ids={mint}", timeout=12)
        data = (r.json() or {}).get("data") or {}
        p = data.get(mint) or {}
        price = p.get("price")
        if price is None:
            return None
        return float(price)
    except Exception:
        return None


def get_price_usd(mint: str):
    """USD price of a token (Jupiter first, DEXScreener fallback). Blocking."""
    p = _jup_price(mint)
    if p:
        return p
    try:
        pair = _dex(mint)
        base = pair.get("baseToken") or {}
        p = base.get("priceUsd")
        if p:
            return float(p)
    except Exception:
        pass
    return None


def get_sol_price_usd() -> float:
    p = _jup_price(SOL_MINT)
    if p:
        return p
    return 0.0


def human_usd(v: float) -> str:
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.1f}K"
    return f"${v:.2f}"


def smart_score(liquidity_usd: float, volume_usd: float, age_days, holders: int) -> int:
    score = 0
    if liquidity_usd >= 100_000:
        score += 8
    elif liquidity_usd >= 10_000:
        score += 5
    elif liquidity_usd > 0:
        score += 3
    if volume_usd >= 100_000:
        score += 8
    elif volume_usd >= 10_000:
        score += 5
    elif volume_usd > 0:
        score += 2
    if age_days is not None:
        if age_days < 1:
            score += 6
        elif age_days < 7:
            score += 4
        elif age_days < 30:
            score += 2
    if holders >= 30:
        score += 4
    elif holders >= 10:
        score += 2
    return min(score, 30)


def build_report(mint: str):
    """Returns a dict with everything needed for /top /kols /dev /full, or None."""
    try:
        pair = _dex(mint)
    except Exception:
        pair = {}
    try:
        largest = token_largest(mint, limit=20)
    except Exception:
        largest = []
    try:
        supply, decimals = token_supply(mint)
    except Exception:
        supply, decimals = 0.0, 0

    price = None
    base = pair.get("baseToken") or {}
    symbol = base.get("symbol") or mint[:6].upper()
    name = base.get("name") or symbol
    price = float(base.get("priceUsd") or 0) or None
    liquidity_usd = float((pair.get("liquidity") or {}).get("usd") or 0)
    volume_usd = float((pair.get("volume") or {}).get("h24") or 0)
    created_ms = pair.get("pairCreatedAt")
    age_days = None
    if created_ms:
        age_days = (time.time() - created_ms / 1000) / 86400

    holders = []
    for h in largest:
        ui = float(h.get("uiAmount") or 0)
        pct = (ui / supply * 100) if supply else 0.0
        usd = ui * price if price else 0.0
        holders.append({
            "address": h.get("address", ""),
            "ui": ui,
            "pct": pct,
            "usd": usd,
        })

    top_vals = {"1": 0.0, "3": 0.0, "10": 0.0, "30": 0.0}
    for n in (1, 3, 10, 30):
        s = sum(h["pct"] for h in holders[:n])
        top_vals[str(n)] = round(s, 1)

    total_usd = sum(h["usd"] for h in holders[:20])

    score = smart_score(liquidity_usd, volume_usd, age_days, len(holders))

    dev = None
    try:
        authority = mint_authority(mint)
        if authority:
            dev = {"authority": authority,
                   "holding": next((h for h in holders if h["address"] == authority), None)}
    except Exception:
        dev = None

    return {
        "mint": mint,
        "name": name,
        "symbol": symbol,
        "price": price,
        "liquidity_usd": liquidity_usd,
        "volume_usd": volume_usd,
        "created_ms": created_ms,
        "age_days": age_days,
        "supply": supply,
        "decimals": decimals,
        "holders": holders,
        "top": top_vals,
        "score": score,
        "total_usd": total_usd,
        "dev": dev,
        "dex_url": pair.get("url", ""),
    }


# ------------------------------------------------------------------ formatters
def holder_line(i: int, h: dict) -> str:
    addr = h["address"][:4] + "…" + h["address"][-4:]
    return (f"#{i} ({human_usd(h['usd'])}) {h['ui']:.2f} SOL | {h['pct']:.1f}% | {addr}")


def holders_block(rep: dict, limit: int = 5) -> str:
    return "\n".join(holder_line(i, h) for i, h in enumerate(rep["holders"][:limit], 1))


def links_line(rep: dict) -> str:
    return "🔗 DEX • AXM • TRO • PDR • PHO • NEO • GMGN • BLZ"


def format_top(rep: dict) -> str:
    t = rep["top"]
    created = ""
    if rep["created_ms"]:
        dt = datetime.fromtimestamp(rep["created_ms"] / 1000, tz=timezone.utc)
        created = f"\n📅 Created: {dt.strftime('%d %b %Y')}"
    return (
        f"@{rep['name']} ({rep['symbol']})\n"
        f"{links_line(rep)}\n"
        f"📈 TOP1 TOP3 TOP10 TOP30\n"
        f"{t['1']}% {t['3']}% {t['10']}% {t['30']}%\n"
        f"HOLDERS: {len(rep['holders'])}+ | SMART SCORE: {rep['score']}/30\n"
        f"💵 Price: ${rep['price']:.8f} | Vol 24h: {human_usd(rep['volume_usd'])} | "
        f"Liq: {human_usd(rep['liquidity_usd'])}{created}\n\n"
        f"{holders_block(rep)}\n"
        f"TOTAL TOP HOLDER VALUE:\n${rep['total_usd']:,.0f}\n\n"
        f"↗️ {config.AD_LINE}"
    )


def format_kols(rep: dict) -> str:
    tagged = [(h, config.KOL_TAGS[h["address"]]) for h in rep["holders"]
              if h["address"] in config.KOL_TAGS]
    lines = []
    if tagged:
        lines.append("👤 KOL REPORT")
        lines.append(f"@{rep['name']} ({rep['symbol']})\n")
        for h, name in tagged:
            lines.append(f"• {name}: {h['ui']:.2f} ({h['pct']:.1f}%) — "
                         f"{human_usd(h['usd'])}")
        lines.append("\nTag more KOLs in .env → KOL_TAGS=Wallet=Name,Wallet2=Name2")
    else:
        lines.append("👤 KOL REPORT")
        lines.append(f"@{rep['name']} ({rep['symbol']})\n")
        lines.append("No tagged KOLs found in this token's top holders.")
        lines.append("\nTop holders (tag them in .env KOL_TAGS):\n")
        lines.extend(holder_line(i, h) for i, h in enumerate(rep["holders"][:10], 1))
    return "\n".join(lines)


def format_dev(rep: dict) -> str:
    lines = ["🛠 DEV REPORT", f"@{rep['name']} ({rep['symbol']})\n"]
    dev = rep.get("dev")
    if not dev or not dev.get("authority"):
        lines.append("👷 Dev wallet: n/a (mint authority renounced or not found)")
    else:
        lines.append(f"👷 Dev wallet: {dev['authority'][:6]}…{dev['authority'][-6:]}")
        h = dev.get("holding")
        if h:
            lines.append(f"💰 Holding: {h['ui']:.2f} {rep['symbol']} "
                         f"({h['pct']:.1f}% — {human_usd(h['usd'])})")
        else:
            lines.append("💰 Holding: none detected")
    if rep["created_ms"]:
        dt = datetime.fromtimestamp(rep["created_ms"] / 1000, tz=timezone.utc)
        lines.append(f"📅 Created: {dt.strftime('%d %b %Y %H:%M UTC')}")
    lines.append(f"💧 Liquidity: {human_usd(rep['liquidity_usd'])}")
    lines.append(f"📦 Supply: {rep['supply']:,.0f} {rep['symbol']}")
    lines.append(f"\n↗️ {config.AD_LINE}")
    return "\n".join(lines)


def format_full(rep: dict) -> str:
    return (
        f"📑 FULL REPORT\n@{rep['name']} ({rep['symbol']})\n\n"
        f"🛠 DEV:\n{format_dev(rep)}\n\n"
        f"👤 KOLS:\n{format_kols(rep)}\n\n"
        f"📊 HOLDERS:\n{format_top(rep)}"
    )
