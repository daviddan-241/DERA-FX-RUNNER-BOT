"""
Solana helpers: RPC, treasury wallet import, balances, real on-chain payment
verification, SOL/SPL transfers and Jupiter swaps (BUY/SELL).
All functions are blocking (requests/solders) — call them via asyncio.to_thread.
"""
import base64
import json
import struct
from decimal import Decimal

import requests
from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.message import to_bytes_versioned
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction, VersionedTransaction

import config

SOL_MINT = "So11111111111111111111111111111111111111112"
LAMPORTS_PER_SOL = Decimal(1_000_000_000)
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATA_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")

# ------------------------------------------------------------------ money
def sol_to_lam(sol) -> int:
    return int(Decimal(str(sol)) * LAMPORTS_PER_SOL)


def lam_to_sol(lam) -> float:
    return float(Decimal(str(lam)) / LAMPORTS_PER_SOL)


# ------------------------------------------------------------------ rpc
def rpc(method: str, params: list = None):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    r = requests.post(config.RPC_URL, json=body, timeout=12)
    r.raise_for_status()
    data = r.json()
    if "error" in data and data["error"]:
        raise RuntimeError(str(data["error"])[:300])
    return data.get("result")


# ------------------------------------------------------------------ wallets
def keypair_from_secret(secret: str) -> Keypair:
    """Accepts:
      • a BIP39 seed phrase (12/24 words) — derived with the STANDARD Solana
        BIP44 path m/44'/501'/0'/0', exactly like Phantom/Solflare/Backpack,
        so an imported seed gives the user their REAL wallet address
      • base58 private key (Phantom/Backpack format)
      • base64 private key (64 bytes)
      • a JSON byte-array [1,2,3,...] (the format the bot exports)
      • a python bytes literal b'...'
    """
    secret = secret.strip()
    if not secret:
        raise ValueError("empty key")
    # seed phrase?
    words = secret.split()
    if 12 <= len(words) <= 24 and all(w.isalpha() for w in words):
        try:
            from mnemonic import Mnemonic
        except ImportError:
            raise ValueError("mnemonic package missing (pip install mnemonic)")
        m = Mnemonic("english")
        if m.check(secret):
            seed = m.to_seed(secret)
            try:
                # standard wallet derivation — matches Phantom & friends
                return Keypair.from_seed_and_derivation_path(
                    seed, "m/44'/501'/0'/0'")
            except Exception:
                return Keypair.from_seed(seed[:32])
        raise ValueError("invalid seed phrase (check the words and try again)")
    if secret.startswith("["):
        arr = json.loads(secret)
        if not isinstance(arr, list) or len(arr) != 64:
            raise ValueError("byte array must have 64 numbers")
        return Keypair.from_bytes(bytes(int(x) & 0xFF for x in arr))
    try:
        return Keypair.from_base58_string(secret)
    except Exception:
        pass
    try:
        import base64
        raw = base64.b64decode(secret, validate=True)
        if len(raw) == 64:
            return Keypair.from_bytes(raw)
    except Exception:
        pass
    if secret.startswith("b'") and secret.endswith("'"):
        inner = secret[2:-1]
        if not inner.startswith("["):
            inner = "[" + inner + "]"
        try:
            arr = json.loads(inner)
            return Keypair.from_bytes(bytes(int(x) & 0xFF for x in arr))
        except Exception:
            pass
    raise ValueError("not a valid seed phrase, base58/base64 key or byte array")


def extract_secret(text: str) -> str:
    """People paste keys surrounded by other text ("Secret key: xxx", labels,
    extra lines). Pull the actual key material out and return JUST that."""
    import re
    t = (text or "").strip()
    if not t:
        return t
    # a line that is exactly 12/24 seed words
    for line in t.splitlines():
        s = line.strip()
        s = s.strip('`').strip('"').strip("'")
        words = s.split()
        if 12 <= len(words) <= 24 and all(w.isalpha() for w in words):
            return s
    # a [64 numbers] array anywhere in the text
    m = re.search(r"\[\s*-?\d+(?:\s*,\s*-?\d+){63}\s*\]", t)
    if m:
        return m.group(0)
    # the longest base58-ish token (87-88 char keys; allows base64 too)
    tokens = re.findall(r"[A-Za-z0-9+/=]{80,128}", t)
    if tokens:
        return max(tokens, key=len)
    return t


def derive_user_keypair(seed_phrase: str, user_id: int) -> Keypair:
    """Deterministically derive a UNIQUE wallet per user from the master seed
    in .env (WALLET_SEED): sha256(master_seed | user_id) -> ed25519 keypair."""
    import hashlib
    digest = hashlib.sha256(f"{seed_phrase.strip()}|{user_id}".encode()).digest()
    return Keypair.from_seed(digest)


def new_keypair() -> Keypair:
    return Keypair()


def sol_balance(addr: str) -> int:
    """Balance in lamports — retried once so one RPC hiccup doesn't zero
    someone's panel."""
    last = None
    for attempt in range(2):
        try:
            res = rpc("getBalance", [str(addr)])
            return int(res["value"])
        except Exception as e:
            last = e
    raise last


def token_accounts(owner: str):
    """List SPL token accounts with uiAmount > 0 for owner."""
    try:
        res = rpc("getTokenAccountsByOwner", [
            owner,
            {"programId": str(TOKEN_PROGRAM)},
            {"encoding": "jsonParsed"},
        ])
    except Exception:
        return []
    out = []
    for acc in res.get("value", []):
        info = acc["account"]["data"]["parsed"]["info"]
        amt = float(info["tokenAmount"]["uiAmount"] or 0)
        if amt <= 0:
            continue
        out.append({
            "ata": acc["pubkey"],
            "mint": info["mint"],
            "amount": int(info["tokenAmount"]["amount"]),
            "decimals": info["tokenAmount"]["decimals"],
            "ui": amt,
        })
    return out


def token_supply(mint: str):
    res = rpc("getTokenSupply", [mint])["value"]
    return float(res["uiAmount"] or 0), res["decimals"]


def token_largest(mint: str, limit: int = 20):
    return rpc("getTokenLargestAccounts", [mint, {"commitment": config.MIN_CONFIRM_LEVEL}])["value"]


def mint_authority(mint: str):
    try:
        res = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        val = res["value"]
        if not val:
            return None
        return val["data"]["parsed"]["info"].get("mintAuthority")
    except Exception:
        return None


def mint_exists(mint: str) -> bool:
    try:
        res = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        return bool(res.get("value"))
    except Exception:
        return False


# ------------------------------------------------------------------ SPL helpers (manual builders — solders dropped them)
def get_ata(owner: Pubkey, mint: Pubkey) -> Pubkey:
    ata, _ = Pubkey.find_program_address(
        [bytes(owner), bytes(TOKEN_PROGRAM), bytes(mint)], ATA_PROGRAM)
    return ata


def create_ata_ix(payer: Pubkey, owner: Pubkey, mint: Pubkey) -> Instruction:
    ata = get_ata(owner, mint)
    return Instruction(ATA_PROGRAM, b"\x00", [
        AccountMeta(payer, True, True),
        AccountMeta(ata, False, True),
        AccountMeta(owner, False, False),
        AccountMeta(mint, False, False),
        AccountMeta(SYSTEM_PROGRAM, False, False),
        AccountMeta(TOKEN_PROGRAM, False, False),
    ])


def transfer_checked_ix(amount: int, decimals: int, source: Pubkey, mint: Pubkey,
                        dest: Pubkey, owner: Pubkey) -> Instruction:
    data = struct.pack("<BQB", 12, amount, decimals)
    return Instruction(TOKEN_PROGRAM, data, [
        AccountMeta(source, False, True),
        AccountMeta(mint, False, False),
        AccountMeta(dest, False, True),
        AccountMeta(owner, True, False),
    ])


# ------------------------------------------------------------------ transactions
def latest_blockhash() -> Hash:
    res = rpc("getLatestBlockhash", [{"commitment": "confirmed"}])["value"]
    return Hash.from_string(res["blockhash"])


def send_raw_b64(b64: str) -> str:
    return rpc("sendTransaction", [b64, {"encoding": "base64",
                                         "preflightCommitment": "confirmed",
                                         "maxRetries": 3}])


def transfer_sol(from_kp: Keypair, to: str, lamports: int) -> str:
    bh = latest_blockhash()
    ix = transfer(TransferParams(
        from_pubkey=from_kp.pubkey(),
        to_pubkey=Pubkey.from_string(to),
        lamports=lamports,
    ))
    tx = Transaction.new_signed_with_payer(
        [ix], payer=from_kp.pubkey(), signing_keypairs=[from_kp], recent_blockhash=bh
    )
    return send_raw_b64(base64.b64encode(bytes(tx)).decode())


def transfer_token(from_kp: Keypair, to: str, mint: str, amount: int, decimals: int) -> str:
    mint_pk = Pubkey.from_string(mint)
    to_pk = Pubkey.from_string(to)
    src = get_ata(from_kp.pubkey(), mint_pk)
    dst = get_ata(to_pk, mint_pk)
    ixs = []
    if rpc("getAccountInfo", [str(dst)])["value"] is None:
        ixs.append(create_ata_ix(from_kp.pubkey(), to_pk, mint_pk))
    ixs.append(transfer_checked_ix(amount, decimals, src, mint_pk, dst, from_kp.pubkey()))
    bh = latest_blockhash()
    tx = Transaction.new_signed_with_payer(
        ixs, payer=from_kp.pubkey(), signing_keypairs=[from_kp], recent_blockhash=bh
    )
    return send_raw_b64(base64.b64encode(bytes(tx)).decode())


# ------------------------------------------------------------------ payment verification (real txs)
def recent_signatures(addr: str, limit: int = 100):
    res = rpc("getSignaturesForAddress", [
        addr, {"limit": limit, "commitment": config.MIN_CONFIRM_LEVEL},
    ])
    return res or []


def get_tx(sig: str):
    try:
        return rpc("getTransaction", [
            sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0,
                  "commitment": config.MIN_CONFIRM_LEVEL},
        ])
    except Exception:
        return None


def incoming_sol_diff(tx: dict, addr: str) -> int:
    """Lamports received by `addr` in this tx (SOL only). 0 if none."""
    try:
        meta = tx["meta"]
        if meta is None or meta.get("err") is not None:
            return 0
        keys = tx["transaction"]["message"]["accountKeys"]
        pre = meta.get("preBalances") or []
        post = meta.get("postBalances") or []
        for i, k in enumerate(keys):
            pk = k if isinstance(k, str) else k.get("pubkey")
            if pk == addr and i < len(pre) and i < len(post):
                diff = post[i] - pre[i]
                return diff if diff > 0 else 0
    except Exception:
        pass
    return 0


def scan_treasury_for_payment(treasury: str, required_lamports: int,
                              used_sigs: set, min_ts: int):
    """Find a real, recent, unused on-chain SOL transfer to the treasury that
    covers the required amount. Returns (sig, lamports, payer) or None."""
    for s in recent_signatures(treasury, limit=100):
        sig = s.get("signature")
        if not sig or sig in used_sigs:
            continue
        ts = s.get("blockTime") or 0
        if ts and ts < min_ts:
            break  # signatures are newest-first
        if s.get("err") is not None:
            continue
        tx = get_tx(sig)
        if not tx:
            continue
        diff = incoming_sol_diff(tx, treasury)
        if diff < required_lamports:
            continue
        keys = tx["transaction"]["message"]["accountKeys"]
        payer = keys[0] if isinstance(keys[0], str) else keys[0].get("pubkey", "")
        return sig, diff, payer
    return None


def verify_single_tx(sig: str, treasury: str):
    tx = get_tx(sig)
    if not tx:
        return None
    meta = tx.get("meta") or {}
    if meta.get("err") is not None:
        return {"ok": False, "reason": "tx error", "ts": meta.get("blockTime")}
    diff = incoming_sol_diff(tx, treasury)
    keys = tx["transaction"]["message"]["accountKeys"]
    payer = keys[0] if isinstance(keys[0], str) else keys[0].get("pubkey", "")
    return {"ok": diff > 0, "lamports": diff, "payer": payer, "ts": meta.get("blockTime")}


# ------------------------------------------------------------------ Jupiter (real swaps)
def jupiter_quote(input_mint: str, output_mint: str, amount_lamports: int,
                  slippage_bps: int, only_direct: bool = False) -> dict:
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_lamports),
        "slippageBps": str(slippage_bps),
    }
    if only_direct:
        params["onlyDirectRoutes"] = "true"
    r = requests.get("https://quote-api.jup.ag/v6/quote", params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data.get("error") or "quote error")
    return data


def jupiter_swap(kp: Keypair, quote: dict) -> str:
    r = requests.post("https://quote-api.jup.ag/v6/swap", json={
        "quoteResponse": quote,
        "userPublicKey": str(kp.pubkey()),
        "wrapAndUnwrapSol": True,
        "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": "auto",
    }, timeout=25)
    r.raise_for_status()
    data = r.json()
    if "error" in data or not data.get("swapTransaction"):
        raise RuntimeError(data.get("error") or "no swap transaction returned")
    tx = VersionedTransaction.from_bytes(base64.b64decode(data["swapTransaction"]))
    msg_bytes = to_bytes_versioned(tx.message)
    sig = kp.sign_message(msg_bytes)
    signed = VersionedTransaction.populate(tx.message, [sig])
    return send_raw_b64(base64.b64encode(bytes(signed)).decode())


# ------------------------------------------------------------------ treasury (imported wallet)
def treasury_keypair_from(secret: str) -> Keypair:
    """The bot's receiving wallet: set via /importwallet (DB) or TREASURY_PRIVATE_KEY (.env)."""
    if not secret:
        raise RuntimeError("treasury wallet not configured")
    return keypair_from_secret(secret)


def treasury_address_from(secret: str) -> str:
    return str(treasury_keypair_from(secret).pubkey())


def validate_secret(secret: str) -> str:
    kp = keypair_from_secret(secret)
    return str(kp.pubkey())
