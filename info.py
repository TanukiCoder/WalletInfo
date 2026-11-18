#!/usr/bin/env python3
"""Генерация адресов из secp256k1 приватного ключа и проверка балансов через публичные RPC/API.
Вывод: адреса + только положительные балансы (включая пыль).

Разработчик: TG: @TanukiCode / Site: Tanuki.host
Telegram: https://t.me/TanukiCode
Сайт: https://tanuki.host
"""

from __future__ import annotations

DEVELOPER = "TG: @TanukiCode / Site: Tanuki.host"
DEVELOPER_LINKS = "Telegram: https://t.me/TanukiCode / Site: https://tanuki.host"

import argparse
import asyncio
import hashlib
import json
import re
import ssl
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

import aiohttp
import base58
from eth_account import Account
from eth_keys import keys as eth_keys

Account.enable_unaudited_hdwallet_features()


@dataclass(frozen=True)
class AddrSpec:
    network: str
    variant: str
    address: str


@dataclass(frozen=True)
class CheckTask:
    asset_label: str
    group: str | None
    network: str
    variant: str
    address: str
    decimals: int
    kind: str
    url: str
    payload: dict[str, Any] | None = None


USDT_ERC20 = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
USDT_BEP20 = "0x55d398326f99059fF775485246999027B3197955"
USDT_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

EVM_CHAINS: list[tuple[str, str, str]] = [
    ("ETH", "ethereum", "https://ethereum.publicnode.com"),
    ("BNB", "bsc", "https://bsc.publicnode.com"),
    ("MATIC", "polygon", "https://polygon-bor.publicnode.com"),
    ("ETH Arbitrum", "arbitrum", "https://arbitrum-one.publicnode.com"),
    ("ETH Optimism", "optimism", "https://optimism.publicnode.com"),
    ("AVAX", "avalanche", "https://avalanche-c-chain.publicnode.com"),
    ("ETH Base", "base", "https://base.publicnode.com"),
    ("FTM", "fantom", "https://rpc.fantom.network"),
    ("xDAI", "gnosis", "https://gnosis-rpc.publicnode.com"),
    ("ETH Linea", "linea", "https://linea-rpc.publicnode.com"),
    ("ETH Scroll", "scroll", "https://scroll-rpc.publicnode.com"),
    ("ETH zkSync", "zksync", "https://mainnet.era.zksync.io"),
    ("ETH Polygon zkEVM", "polygon-zkevm", "https://polygon-zkevm-bor.publicnode.com"),
    ("MNT", "mantle", "https://mantle-rpc.publicnode.com"),
    ("ETH Blast", "blast", "https://blast-rpc.publicnode.com"),
    ("ETH Mode", "mode", "https://mode-rpc.publicnode.com"),
    ("CELO", "celo", "https://celo-rpc.publicnode.com"),
    ("GLMR", "moonbeam", "https://moonbeam-rpc.publicnode.com"),
    ("MOVR", "moonriver", "https://moonriver-rpc.publicnode.com"),
    ("CRO", "cronos", "https://cronos-evm-rpc.publicnode.com"),
    ("KAVA", "kava", "https://kava-evm-rpc.publicnode.com"),
    ("ONE", "harmony", "https://harmony-0-rpc.publicnode.com"),
    ("METIS", "metis", "https://andromeda.metis.io/?owner=1088"),
    ("ETH Boba", "boba", "https://boba-eth.drpc.org"),
    ("BNB opBNB", "opbnb", "https://opbnb-rpc.publicnode.com"),
    ("ETH Taiko", "taiko", "https://taiko-rpc.publicnode.com"),
    ("ETH Manta", "manta", "https://pacific-rpc.manta.network/http"),
    ("PLS", "pulsechain", "https://rpc.pulsechain.com"),
    ("TLOS", "telos", "https://telos-evm-rpc.publicnode.com"),
    ("RON", "ronin", "https://api.roninchain.com/rpc"),
]

WETH_L2 = "0x4200000000000000000000000000000000000006"

PER_CHAIN_TOKENS: dict[str, dict[str, tuple[str, int]]] = {
    "ethereum": {
        "USDT": (USDT_ERC20, 6),
        "USDC": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
        "DAI": ("0x6B175474E89094C44Da98b954EedeAC495271d0F", 18),
        "WETH": ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18),
    },
    "bsc": {
        "USDT": (USDT_BEP20, 18),
        "USDC": ("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", 18),
        "WETH": ("0x2170Ed0880ac9A755fd29B2688956BD959F73363", 18),
        "WBNB": ("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", 18),
    },
    "polygon": {
        "USDT": ("0xc2132D05D31c914a87C6611C10748AEb04B58e8F", 6),
        "USDC": ("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6),
        "WETH": ("0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619", 18),
    },
    "arbitrum": {
        "USDT": ("0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", 6),
        "USDC": ("0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
        "WETH": ("0x82aF49447D8a07e3bd95BD0d56f45241543f6094", 18),
    },
    "optimism": {
        "USDT": ("0x94b008aA305d0A04fB5cDA75fd2c5AF3A430c428", 6),
        "USDC": ("0x0b2C639c533813f4Aa9D7837CA676ab94cdd52C0", 6),
        "WETH": (WETH_L2, 18),
    },
    "avalanche": {
        "USDT": ("0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7", 6),
        "USDC": ("0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", 6),
        "WETH": ("0x49D5c2BdFfac6CE2BFdB6640F4F2f2b773564398", 18),
    },
    "base": {
        "USDT": ("0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2", 6),
        "USDC": ("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
        "WETH": (WETH_L2, 18),
    },
    "fantom": {
        "USDT": ("0x049d36570d4e46f48e99674ad3ac8bD65a783612", 6),
        "USDC": ("0x04068DA006CdA8CAf721e9dDf62b536BBd571988", 6),
        "WETH": ("0x74b23882a30290451A17c44f4F70643bF9FD9e47", 18),
    },
    "gnosis": {
        "USDT": ("0x4ECBa0BB60BA44A6680856BE91eE3852db4C4BA8", 6),
        "USDC": ("0xDDAfbb505ad214D7Bc80e80Fc402aCF4Bfb00000", 6),
        "WETH": ("0xe91D153E0b41518A2Ce8Dd3D7924dd132AA661470", 18),
    },
    "linea": {
        "USDT": ("0xA219439258ca9da29E9Cc4cE5596924745e12B93", 6),
        "USDC": ("0x176211869cA2b568f2A7D4EE941E073a821EE685", 6),
        "WETH": ("0xe5D7C2a44B9A0Ba0E1E5bAE2B8D1F56C3F08483", 18),
    },
    "scroll": {
        "USDT": ("0xf55Bec9c4076b27e3f2a351e83b8154d5a1cc5d", 6),
        "USDC": ("0x06eFdBFf2a14a7c8E29244aE962D58aDC4DDBF84", 6),
        "WETH": ("0x5300000000000000000000000000000000000004", 18),
    },
    "zksync": {
        "USDT": ("0x493257fD37EDB34451fE2CA2397C53845b79b8a4", 6),
        "USDC": ("0x3355df6DDE22E345c4eBA3fa37fb5a7278e9B15D", 6),
        "WETH": ("0x5AEa5775959fFBBC5c66F774f0858dD69Ff5Ecf", 18),
    },
    "polygon-zkevm": {
        "USDT": ("0x1E4a5963aBFD975dE6B91B4E3e083B2674D9e4F1", 6),
        "USDC": ("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6),
        "WETH": ("0x4F9A0e7f2CE367EE7FFe3Fae9eA23eb0C7e1D1176", 18),
    },
    "mantle": {
        "USDT": ("0x201EBa5CC46D216Ce6DC203cE52F1B0b0F711bAb", 6),
        "USDC": ("0x09Bc4E0D86485489Cd5a3431B3Ec7c925B6D00c8", 6),
        "WETH": ("0xdeaddeaddeaddeaddeaddeaddeaddeaddead0000", 18),
    },
    "blast": {
        "USDT": ("0x4300000000000000000000000000000000000003", 6),
        "USDC": ("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
        "WETH": (WETH_L2, 18),
    },
    "mode": {
        "USDT": ("0xf0FDa05e5b887A18A173Aecb07bB62D8A2F3dF7e", 6),
        "USDC": ("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
        "WETH": (WETH_L2, 18),
    },
    "celo": {
        "USDT": ("0x617f3112bf5397D6007a3b3Bf7213A31d3768897", 6),
        "USDC": ("0xceba9300f2b948710d2453e04f5308e7D743359", 6),
    },
    "moonbeam": {
        "USDT": ("0xeE0c4D7f5Cd76bd9A83C1370c499301D29FB0D3E", 6),
        "USDC": ("0x818Ec355Ad33849ef5613918Aa6635D4917A3da8", 6),
        "WETH": ("0x30D2a9F5FDf90ACe8c17952cbb4eE48a55D916A7", 18),
    },
    "moonriver": {
        "USDT": ("0x359A2d2bd41A9E61671fCcC749B8e4e2C4C9B86f", 6),
        "USDC": ("0x818Ec355Ad33849ef5613918Aa6635D4917A3da8", 6),
    },
    "cronos": {
        "USDT": ("0x66e428c3f67a68878562E79A0234c1f83c208590", 6),
        "USDC": ("0xc21223274CAbb028f582ae0FaE2acF8a88a446BE", 6),
    },
    "kava": {
        "USDT": ("0x919c1c267BC06a7039ba03f04eEdd2C87453Edb5", 6),
        "USDC": ("0xf200200e631f897B65B1a4D4aE628c5FF76dEa6C7", 6),
    },
    "harmony": {
        "USDT": ("0x3C2B8Be99cE773970b1DCCaD13c2b9679a2A764a", 6),
        "USDC": ("0x985458E8d4F984fa43Fe59746F537C52F52Cc8A", 6),
    },
    "metis": {
        "USDT": ("0xBB688946871998A22158A8418E0096855f3d1255", 6),
        "USDC": ("0xEA32A96662a47EbC7Bc0ee9c5cBEcBD51E93076F", 6),
        "WETH": ("0x4200000000000000000000000000000000000006", 18),
    },
    "boba": {
        "USDT": ("0x5DE1677344D3Cb8D6aa39b62C4DB8145d1F947f6", 6),
        "USDC": ("0x66a3A5B77b1a5B121dd4FD0c70EEFbA1dCC8f632", 6),
        "WETH": (WETH_L2, 18),
    },
    "opbnb": {
        "USDT": ("0x9e5AAC1BC609bA016C2B2F847f077768D5675964", 18),
        "USDC": ("0x9e5AAC1BC609bA016C2B2F847f077768D5675964", 18),
        "WETH": (WETH_L2, 18),
    },
    "taiko": {
        "USDT": ("0x3b065bbc815408c3ed1110ac08f62D2f95067EeD", 6),
        "USDC": ("0x20cab320bb63c5c9fb1aafe072dac8e95617148", 6),
        "WETH": (WETH_L2, 18),
    },
    "manta": {
        "USDT": ("0xb7360330AaA44c8309726854125292A6fBd5A83d", 6),
        "USDC": ("0xb7360330AaA44c8309726854125292A6fBd5A83d", 6),
        "WETH": (WETH_L2, 18),
    },
    "pulsechain": {
        "USDT": ("0x9159ce8e0183510c0B6b873A7421B9Ae5b36F92E", 6),
        "USDC": ("0x808402F16618c5C10a1da0E65B3e2a3c4E9d4E4e", 6),
    },
    "telos": {
        "USDT": ("0x9235b9974f3eD12cD3E5a4D433F8870EB0a1bA62", 6),
        "USDC": ("0x371E153275489eAA41Bb3136115b9d95e8e208B6", 6),
    },
    "ronin": {
        "USDT": ("0x0B7007c13325C5911105E67Ca6Ef2F6B3668bE2a", 6),
        "USDC": ("0x86E4d5fAF9d413C96e348f4d8416d11D6871e81a", 6),
        "WETH": ("0xc99a6A985eD272443cF6bdaB5Ad8C8c1c17e0488", 18),
    },
}

CHAIN_TOKEN_SUFFIX: dict[str, str] = {
    "ethereum": "ERC20",
    "bsc": "BEP20",
    "polygon": "Polygon",
    "arbitrum": "Arbitrum",
    "optimism": "Optimism",
    "avalanche": "Avalanche",
    "base": "Base",
    "fantom": "Fantom",
    "gnosis": "Gnosis",
    "linea": "Linea",
    "scroll": "Scroll",
    "zksync": "zkSync",
    "polygon-zkevm": "Polygon zkEVM",
    "mantle": "Mantle",
    "blast": "Blast",
    "mode": "Mode",
    "celo": "Celo",
    "moonbeam": "Moonbeam",
    "moonriver": "Moonriver",
    "cronos": "Cronos",
    "kava": "Kava",
    "harmony": "Harmony",
    "metis": "Metis",
    "boba": "Boba",
    "opbnb": "opBNB",
    "taiko": "Taiko",
    "manta": "Manta",
    "pulsechain": "PulseChain",
    "telos": "Telos",
    "ronin": "Ronin",
}

SOLANA_RPC = "https://solana-rpc.publicnode.com"
SOLANA_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SPL_USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
SPL_USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

TRON_TOKENS: list[tuple[str, str, int]] = [
    ("USDT TRC20", USDT_TRC20, 6),
    ("USDC TRC20", "TEkxiTehnzSmSe2XqrBj4w32RUNuuBdYJ", 6),
    ("USDD TRC20", "TR7MV2sPzsXp2y1Qxj6tK4M6snjmXRkAZ", 18),
    ("TUSD TRC20", "TUpMhErZW2mVHdlPd8PrNH3tcjsgADpDa6", 18),
]

UTXO_API_BASE: dict[str, str] = {
    "bitcoin": "https://mempool.space/api/address/",
    "litecoin": "https://litecoinspace.org/api/address/",
}

_tron_account_cache: dict[str, dict[str, Any]] = {}
_tron_lock: asyncio.Lock | None = None

_RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 4
_HOST_CONCURRENCY = 4
_USER_AGENT = "WalletInfo/1.0 (+https://tanuki.host)"


class _Retryable(Exception):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def erc20_balance_of(holder: str, contract: str) -> dict[str, Any]:
    data = "0x70a08231" + holder[2:].lower().zfill(64)
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": contract, "data": data}, "latest"],
    }


def solana_address_from_priv(priv_hex: str) -> str:
    from solders.keypair import Keypair
    return str(Keypair.from_seed(bytes.fromhex(priv_hex)).pubkey())


def is_evm_address(addr: str) -> bool:
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", addr))


def evm_token_label(symbol: str, chain: str) -> str:
    if symbol == "DAI" and chain == "ethereum":
        return "DAI ERC20"
    suffix = CHAIN_TOKEN_SUFFIX.get(chain, chain)
    return f"{symbol} {suffix}"


STABLE_SYMBOLS = frozenset({"USDT", "USDC", "DAI", "USDD", "TUSD"})

COINGECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "BCH": "bitcoin-cash",
    "LTC": "litecoin",
    "DOGE": "dogecoin",
    "DASH": "dash",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "WBNB": "binancecoin",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
    "FTM": "fantom",
    "xDAI": "xdai",
    "CELO": "celo",
    "GLMR": "moonbeam",
    "MOVR": "moonriver",
    "CRO": "crypto-com-chain",
    "KAVA": "kava",
    "ONE": "harmony",
    "METIS": "metis-token",
    "MNT": "mantle",
    "PLS": "pulsechain",
    "TLOS": "telos",
    "RON": "ronin",
    "TRX": "tron",
    "SOL": "solana",
}

L2_ETH_LABELS = frozenset(
    {
        "ETH Arbitrum",
        "ETH Optimism",
        "ETH Base",
        "ETH Linea",
        "ETH Scroll",
        "ETH zkSync",
        "ETH Polygon zkEVM",
        "ETH Blast",
        "ETH Mode",
        "ETH Boba",
        "ETH Taiko",
        "ETH Manta",
    }
)


def normalize_privkey_hex(raw: str) -> str:
    s = raw.strip()
    if s.lower().startswith("0x"):
        s = s[2:]
    if not re.fullmatch(r"[0-9a-fA-F]{64}", s):
        raise ValueError("Ожидается 32-байтный приватный ключ (64 hex-символа, опционально префикс 0x)")
    n = int(s, 16)
    if n <= 0 or n >= 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141:
        raise ValueError("Недопустимое значение приватного ключа для secp256k1")
    return s.lower()


def _rol(value: int, bits: int) -> int:
    value &= 0xFFFFFFFF
    return ((value << bits) | (value >> (32 - bits))) & 0xFFFFFFFF


def _ripemd160_pure(data: bytes) -> bytes:
    """RIPEMD-160 без OpenSSL. На Ubuntu с OpenSSL 3 hashlib часто не имеет ripemd160."""
    h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
    msg = bytearray(data)
    bit_len = len(data) * 8
    msg.append(0x80)
    while (len(msg) % 64) != 56:
        msg.append(0)
    msg += bit_len.to_bytes(8, "little")

    kl = (0x00000000, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E)
    kr = (0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0x00000000)
    rl = (
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
        7, 4, 13, 1, 10, 6, 15, 3, 12, 0, 9, 5, 2, 14, 11, 8,
        3, 10, 14, 4, 9, 15, 8, 1, 2, 7, 0, 6, 13, 11, 5, 12,
        1, 9, 11, 10, 0, 8, 12, 4, 13, 3, 7, 15, 14, 5, 6, 2,
        4, 0, 5, 9, 7, 12, 2, 10, 14, 1, 3, 8, 11, 6, 15, 13,
    )
    rr = (
        5, 14, 7, 0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12,
        6, 11, 3, 7, 0, 13, 5, 10, 14, 15, 8, 12, 4, 9, 1, 2,
        15, 5, 1, 3, 7, 14, 6, 9, 11, 8, 12, 2, 10, 0, 4, 13,
        8, 6, 4, 1, 3, 11, 15, 0, 5, 12, 2, 13, 9, 7, 10, 14,
        12, 15, 10, 4, 1, 5, 8, 7, 6, 2, 13, 14, 0, 3, 9, 11,
    )
    sl = (
        11, 14, 15, 12, 5, 8, 7, 9, 11, 13, 14, 15, 6, 7, 9, 8,
        7, 6, 8, 13, 11, 9, 7, 15, 7, 12, 15, 9, 11, 7, 13, 12,
        11, 13, 6, 7, 14, 9, 13, 15, 14, 8, 13, 6, 5, 12, 7, 5,
        11, 12, 14, 15, 14, 15, 9, 8, 9, 14, 5, 6, 8, 6, 5, 12,
        9, 15, 5, 11, 6, 8, 13, 12, 5, 12, 13, 14, 11, 8, 5, 6,
    )
    sr = (
        8, 9, 9, 11, 13, 15, 15, 5, 7, 7, 8, 11, 14, 14, 12, 6,
        9, 13, 15, 7, 12, 8, 9, 11, 7, 7, 12, 7, 6, 15, 13, 11,
        9, 7, 15, 11, 8, 6, 6, 14, 12, 13, 5, 14, 13, 13, 7, 5,
        15, 5, 8, 11, 14, 14, 6, 14, 6, 9, 12, 9, 12, 5, 15, 8,
        8, 5, 12, 9, 12, 5, 14, 6, 8, 13, 6, 5, 15, 13, 11, 11,
    )

    def f(j: int, x: int, y: int, z: int) -> int:
        if j < 16:
            return x ^ y ^ z
        if j < 32:
            return (x & y) | (~x & z)
        if j < 48:
            return (x | ~y) ^ z
        if j < 64:
            return (x & z) | (y & ~z)
        return x ^ (y | ~z)

    for off in range(0, len(msg), 64):
        words = [int.from_bytes(msg[off + 4 * i: off + 4 * i + 4], "little") for i in range(16)]
        al, bl, cl, dl, el = h
        ar, br, cr, dr, er = h
        for j in range(80):
            tl = (al + f(j, bl, cl, dl) + words[rl[j]] + kl[j // 16]) & 0xFFFFFFFF
            tl = (_rol(tl, sl[j]) + el) & 0xFFFFFFFF
            al, el, dl, cl, bl = el, dl, _rol(cl, 10), bl, tl
            tr = (ar + f(79 - j, br, cr, dr) + words[rr[j]] + kr[j // 16]) & 0xFFFFFFFF
            tr = (_rol(tr, sr[j]) + er) & 0xFFFFFFFF
            ar, er, dr, cr, br = er, dr, _rol(cr, 10), br, tr
        t = (h[1] + cl + dr) & 0xFFFFFFFF
        h[1] = (h[2] + dl + er) & 0xFFFFFFFF
        h[2] = (h[3] + el + ar) & 0xFFFFFFFF
        h[3] = (h[4] + al + br) & 0xFFFFFFFF
        h[4] = (h[0] + bl + cr) & 0xFFFFFFFF
        h[0] = t
    return b"".join(part.to_bytes(4, "little") for part in h)


def ripemd160(data: bytes) -> bytes:
    try:
        return hashlib.new("ripemd160", data, usedforsecurity=False).digest()
    except (ValueError, TypeError, AttributeError):
        return _ripemd160_pure(data)


def hash160(pubkey: bytes) -> bytes:
    return ripemd160(hashlib.sha256(pubkey).digest())


def b58check(version: int, payload: bytes) -> str:
    ver = bytes([version])
    chk = hashlib.sha256(hashlib.sha256(ver + payload).digest()).digest()[:4]
    return base58.b58encode(ver + payload + chk).decode("ascii")


def bech32_hrp_encode(hrp: str, witver: int, witprog: bytes) -> str:
    CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

    def polymod(values: list[int]) -> int:
        gen = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
        chk = 1
        for v in values:
            b = chk >> 25
            chk = ((chk & 0x1FFFFFF) << 5) ^ v
            for i in range(5):
                if (b >> i) & 1:
                    chk ^= gen[i]
        return chk

    def hrp_expand(h: str) -> list[int]:
        return [ord(x) >> 5 for x in h] + [0] + [ord(x) & 31 for x in h]

    def convertbits(data: bytes, frombits: int, tobits: int, pad: bool) -> list[int] | None:
        acc = 0
        bits = 0
        ret: list[int] = []
        maxv = (1 << tobits) - 1
        for byte in data:
            acc = (acc << frombits) | byte
            bits += frombits
            while bits >= tobits:
                bits -= tobits
                ret.append((acc >> bits) & maxv)
        if pad and bits:
            ret.append((acc << (tobits - bits)) & maxv)
        elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
            return None
        return ret

    data = [witver] + (convertbits(witprog, 8, 5, True) or [])
    combined = hrp_expand(hrp) + data
    checksum = polymod(combined + [0, 0, 0, 0, 0, 0]) ^ 1
    checksum_part = [(checksum >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(CHARSET[d] for d in data + checksum_part)


def keccak256(data: bytes) -> bytes:
    from eth_hash.auto import keccak
    return keccak(data)


def tron_address(pubkey_xy: bytes) -> str:
    """Адрес Tron: keccak256 несжатого ключа X||Y (64 байта, без 0x04), затем Base58Check 0x41."""
    if len(pubkey_xy) == 65 and pubkey_xy[0] == 4:
        pubkey_xy = pubkey_xy[1:]
    if len(pubkey_xy) != 64:
        raise ValueError("Для Tron нужен несжатый публичный ключ (64 байта)")
    addr20 = keccak256(pubkey_xy)[-20:]
    return b58check(0x41, addr20)


def eth_address(priv_hex: str) -> str:
    return Account.from_key(priv_hex).address


def collect_addresses(priv_hex: str) -> list[AddrSpec]:
    pk = eth_keys.PrivateKey(bytes.fromhex(priv_hex))
    comp = pk.public_key.to_compressed_bytes()
    uncomp = pk.public_key.to_bytes()

    specs: list[AddrSpec] = []

    eth = eth_address(priv_hex)
    specs.append(AddrSpec("ethereum", "evm", eth))

    for label, pub in (("p2pkh_compressed", comp), ("p2pkh_uncompressed", uncomp)):
        specs.append(AddrSpec("bitcoin", label, b58check(0x00, hash160(pub))))

    h160_c = hash160(comp)
    p2sh = b58check(0x05, hash160(bytes([0x00, 0x14]) + h160_c))
    specs.append(AddrSpec("bitcoin", "p2sh_p2wpkh", p2sh))
    specs.append(AddrSpec("bitcoin", "p2wpkh", bech32_hrp_encode("bc", 0, h160_c)))

    specs.append(AddrSpec("litecoin", "p2pkh", b58check(0x30, hash160(comp))))
    specs.append(AddrSpec("litecoin", "p2wpkh", bech32_hrp_encode("ltc", 0, h160_c)))

    specs.append(AddrSpec("dogecoin", "p2pkh", b58check(0x1E, hash160(comp))))
    specs.append(AddrSpec("dash", "p2pkh", b58check(0x4C, hash160(comp))))

    specs.append(AddrSpec("tron", "base58", tron_address(uncomp)))

    for label, pub in (("p2pkh_compressed", comp), ("p2pkh_uncompressed", uncomp)):
        specs.append(AddrSpec("bitcoin-cash", label, b58check(0x00, hash160(pub))))
    specs.append(AddrSpec("bitcoin-cash", "p2sh_p2wpkh", p2sh))

    return specs


def evm_rpc_map() -> dict[str, str]:
    return {chain: rpc for _, chain, rpc in EVM_CHAINS}


def build_tasks(specs: list[AddrSpec], priv_hex: str) -> list[CheckTask]:
    tasks: list[CheckTask] = []
    eth_addr = next(s.address for s in specs if s.network == "ethereum")
    tron_addr = next(s.address for s in specs if s.network == "tron")
    sol_addr = solana_address_from_priv(priv_hex)
    rpc_map = evm_rpc_map()
    tron_url = f"https://api.trongrid.io/v1/accounts/{tron_addr}"
    token_labels_seen: set[str] = set()

    for asset_label, chain, rpc in EVM_CHAINS:
        tasks.append(
            CheckTask(
                asset_label=asset_label,
                group=f"evm_native:{chain}",
                network=chain,
                variant="native",
                address=eth_addr,
                decimals=18,
                kind="evm",
                url=rpc,
                payload={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_getBalance",
                    "params": [eth_addr, "latest"],
                },
            )
        )

    for chain_key, symbols in PER_CHAIN_TOKENS.items():
        rpc = rpc_map.get(chain_key)
        if not rpc:
            continue
        for symbol, (contract, decimals) in symbols.items():
            label = evm_token_label(symbol, chain_key)
            if label in token_labels_seen:
                continue
            if not is_evm_address(contract):
                print(f"пропуск {label}: некорректный адрес контракта", file=sys.stderr)
                continue
            token_labels_seen.add(label)
            safe = re.sub(r"[^a-zA-Z0-9]+", "_", label)
            tasks.append(
                CheckTask(
                    asset_label=label,
                    group=f"token:{safe}",
                    network=chain_key,
                    variant=contract,
                    address=eth_addr,
                    decimals=decimals,
                    kind="evm_erc20",
                    url=rpc,
                    payload=erc20_balance_of(eth_addr, contract),
                )
            )

    tasks.append(
        CheckTask(
            asset_label="SOL",
            group="sol_native",
            network="solana",
            variant="native",
            address=sol_addr,
            decimals=9,
            kind="sol_native",
            url=SOLANA_RPC,
            payload={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [sol_addr, {"commitment": "confirmed"}],
            },
        )
    )
    for label, mint, decimals in (
        ("USDT Solana", SPL_USDT, 6),
        ("USDC Solana", SPL_USDC, 6),
    ):
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", label)
        tasks.append(
            CheckTask(
                asset_label=label,
                group=f"spl:{safe}",
                network="solana",
                variant=mint,
                address=sol_addr,
                decimals=decimals,
                kind="sol_spl",
                url=SOLANA_RPC,
                payload={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenAccountsByOwner",
                    "params": [
                        sol_addr,
                        {"mint": mint},
                        {"encoding": "jsonParsed", "commitment": "confirmed"},
                    ],
                },
            )
        )

    for label, contract, decimals in TRON_TOKENS:
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", label)
        tasks.append(
            CheckTask(
                asset_label=label,
                group=f"trc20:{safe}",
                network="tron",
                variant=contract,
                address=tron_addr,
                decimals=decimals,
                kind="tron_trc20",
                url=tron_url,
            )
        )

    tasks.append(
        CheckTask(
            asset_label="TRX",
            group="trx_native",
            network="tron",
            variant="native",
            address=tron_addr,
            decimals=6,
            kind="tron_api",
            url=tron_url,
        )
    )

    utxo_groups = {
        "bitcoin": ("BTC", "btc"),
        "bitcoin-cash": ("BCH", "bch"),
        "litecoin": ("LTC", "ltc"),
    }

    for spec in specs:
        if spec.network in ("ethereum", "tron"):
            continue

        if spec.network == "dogecoin":
            tasks.append(
                CheckTask(
                    asset_label="DOGE",
                    group="doge",
                    network=spec.network,
                    variant=spec.variant,
                    address=spec.address,
                    decimals=8,
                    kind="blockcypher",
                    url=f"https://api.blockcypher.com/v1/doge/main/addrs/{spec.address}/balance",
                )
            )
            continue

        if spec.network == "dash":
            tasks.append(
                CheckTask(
                    asset_label="DASH",
                    group="dash",
                    network=spec.network,
                    variant=spec.variant,
                    address=spec.address,
                    decimals=8,
                    kind="blockcypher",
                    url=f"https://api.blockcypher.com/v1/dash/main/addrs/{spec.address}/balance",
                )
            )
            continue

        if spec.network == "bitcoin-cash":
            tasks.append(
                CheckTask(
                    asset_label="BCH",
                    group="bch",
                    network=spec.network,
                    variant=spec.variant,
                    address=spec.address,
                    decimals=8,
                    kind="blockchair_bch",
                    url=f"https://api.blockchair.com/bitcoin-cash/dashboards/address/{spec.address}",
                )
            )
            continue

        base_url = UTXO_API_BASE.get(spec.network, "")
        if not base_url:
            continue

        asset_label, group = utxo_groups.get(spec.network, (spec.network.upper(), spec.network))
        tasks.append(
            CheckTask(
                asset_label=asset_label,
                group=group,
                network=spec.network,
                variant=spec.variant,
                address=spec.address,
                decimals=8,
                kind="utxo_api",
                url=base_url + spec.address,
            )
        )

    return tasks


def format_amount(raw: int, decimals: int) -> str:
    if raw == 0:
        return "0"
    scale = Decimal(10) ** decimals
    q = (Decimal(raw) / scale).normalize()
    return format(q, "f").rstrip("0").rstrip(".") or "0"


def parse_utxo_balance(data: dict[str, Any]) -> int:
    chain = data.get("chain_stats") or {}
    mempool = data.get("mempool_stats") or {}
    funded = int(chain.get("funded_txo_sum", 0)) + int(mempool.get("funded_txo_sum", 0))
    spent = int(chain.get("spent_txo_sum", 0)) + int(mempool.get("spent_txo_sum", 0))
    return max(0, funded - spent)


def parse_tron_balance(data: dict[str, Any]) -> int:
    items = data.get("data") or []
    if not items:
        return 0
    return int(items[0].get("balance", 0) or 0)


def parse_tron_trc20_balance(data: dict[str, Any], contract: str) -> int:
    items = data.get("data") or []
    if not items:
        return 0
    trc20 = items[0].get("trc20") or []
    for entry in trc20:
        if isinstance(entry, dict):
            for addr, amount in entry.items():
                if addr == contract:
                    return int(amount or 0)
    return 0


def parse_sol_native_balance(body: dict[str, Any]) -> int:
    result = body.get("result") or {}
    if isinstance(result, int):
        return result
    return int(result.get("value", 0) or 0)


def parse_sol_spl_balance(body: dict[str, Any]) -> int:
    entries = (body.get("result") or {}).get("value") or []
    total = 0
    for entry in entries:
        try:
            info = entry["account"]["data"]["parsed"]["info"]["tokenAmount"]
            total += int(info.get("amount", 0) or 0)
        except (KeyError, TypeError, ValueError):
            continue
    return total


def parse_blockchair_bch_balance(data: dict[str, Any], address: str) -> int:
    rows = (data.get("data") or {}).get(address) or {}
    addr = rows.get("address") or {}
    return int(addr.get("balance", 0) or 0)


def _retry_after(headers: Any) -> float | None:
    raw = headers.get("Retry-After") if headers is not None else None
    if raw is None:
        return None
    try:
        return min(20.0, max(0.0, float(raw)))
    except (TypeError, ValueError):
        return None


def _rpc_retryable(err: object) -> bool:
    text = str(err).lower()
    needles = ("rate", "limit", "too many", "timeout", "temporarily", "busy", "429", "overloaded", "try again")
    return any(needle in text for needle in needles)


async def _raise_if_retryable(resp: aiohttp.ClientResponse) -> None:
    if resp.status in _RETRY_STATUSES:
        raise _Retryable(f"HTTP {resp.status}", _retry_after(resp.headers))


async def _read_json(resp: aiohttp.ClientResponse, url: str) -> Any:
    try:
        return await resp.json(content_type=None)
    except (aiohttp.ContentTypeError, json.JSONDecodeError, UnicodeError) as exc:
        if resp.status == 200 or resp.status >= 500:
            raise _Retryable(f"плохой JSON от {url}") from exc
        raise RuntimeError(f"плохой JSON от {url}") from exc


def _request_timeout(kind: str) -> aiohttp.ClientTimeout:
    total = 45 if kind == "blockchair_bch" else 30
    return aiohttp.ClientTimeout(total=total, connect=10, sock_read=25)


async def fetch_tron_account(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    global _tron_lock
    if _tron_lock is None:
        _tron_lock = asyncio.Lock()
    async with _tron_lock:
        cached = _tron_account_cache.get(url)
        if cached is not None:
            return cached
        timeout = _request_timeout("tron_api")
        async with session.get(url, timeout=timeout) as resp:
            await _raise_if_retryable(resp)
            if resp.status in (404, 400):
                data: dict[str, Any] = {"data": []}
            else:
                if resp.status >= 400:
                    detail = (await resp.text())[:180]
                    raise RuntimeError(f"HTTP {resp.status} {url}: {detail}")
                data = await _read_json(resp, url)
        if not isinstance(data, dict):
            raise RuntimeError(f"tron: неожиданный ответ {data!r}")
        _tron_account_cache[url] = data
        return data


def is_stablecoin_label(label: str) -> bool:
    u = label.upper()
    if "WETH" in u:
        return False
    return any(tok in u for tok in ("USDT", "USDC", "DAI", "USDD", "TUSD"))


def usd_unit_price(label: str, by_id: dict[str, Decimal]) -> Decimal:
    if "WBNB" in label.upper():
        return by_id.get("binancecoin", Decimal(0))
    if is_stablecoin_label(label):
        return Decimal(1)
    if label.startswith("WETH") or label in L2_ETH_LABELS:
        return by_id.get("ethereum", Decimal(0))
    if label in COINGECKO_IDS:
        return by_id.get(COINGECKO_IDS[label], Decimal(0))
    base = label.split()[0]
    if base in COINGECKO_IDS:
        return by_id.get(COINGECKO_IDS[base], Decimal(0))
    if base == "ETH" or label.startswith("ETH "):
        return by_id.get("ethereum", Decimal(0))
    return Decimal(0)


async def fetch_usd_prices(session: aiohttp.ClientSession) -> dict[str, Decimal]:
    ids = sorted(set(COINGECKO_IDS.values()))
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": ",".join(ids), "vs_currencies": "usd"}
    data: Any = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20, connect=10)) as resp:
                await _raise_if_retryable(resp)
                if resp.status >= 400:
                    raise RuntimeError(f"HTTP {resp.status}")
                data = await _read_json(resp, url)
            break
        except _Retryable as exc:
            if attempt + 1 >= _MAX_ATTEMPTS:
                return {}
            await asyncio.sleep(exc.retry_after if exc.retry_after is not None else min(8.0, 0.5 * (2 ** attempt)))
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError):
            if attempt + 1 >= _MAX_ATTEMPTS:
                return {}
            await asyncio.sleep(min(8.0, 0.5 * (2 ** attempt)))
        except Exception:
            return {}
    out: dict[str, Decimal] = {}
    if isinstance(data, dict):
        for coin_id, row in data.items():
            if isinstance(row, dict) and "usd" in row:
                out[coin_id] = Decimal(str(row["usd"]))
    return out


def format_usd_value(value: Decimal) -> str:
    """Форматирует USD-значение. Для пыли — больше знаков."""
    if value == 0:
        return "0"
    if value < Decimal("0.000001"):
        return f"{value:.8f}".rstrip("0").rstrip(".")
    if value < Decimal("0.01"):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    q = value.quantize(Decimal("0.01"))
    return f"{q:,.2f}"


class BalanceSink:
    def __init__(self, tasks: list[CheckTask]) -> None:
        self._group_totals: dict[str, int] = {}
        self._group_decimals: dict[str, int] = {}
        self._group_label: dict[str, str] = {}
        self._group_pending: dict[str, int] = {}
        self._order: list[str] = []

        for task in tasks:
            key = task.group or f"single:{id(task)}"
            if key not in self._order:
                self._order.append(key)
            self._group_pending[key] = self._group_pending.get(key, 0) + 1
            self._group_decimals[key] = task.decimals
            self._group_label[key] = task.asset_label
            self._group_totals.setdefault(key, 0)
        self._errors: list[str] = []

    def ingest(self, task: CheckTask, raw: int, err: str | None) -> None:
        key = task.group or f"single:{id(task)}"
        self._group_pending[key] -= 1
        if err:
            self._errors.append(f"{task.asset_label}: {err}")
            return
        self._group_totals[key] += raw

    def report_errors(self) -> None:
        if not self._errors:
            return
        print(
            f"Не удалось проверить запросов: {len(self._errors)}. Эти сети не считайте пустыми.",
            file=sys.stderr,
        )
        for line in self._errors[:12]:
            print(f"  {line}", file=sys.stderr)
        extra = len(self._errors) - 12
        if extra > 0:
            print(f"  … и ещё {extra}", file=sys.stderr)

    def print_positive(self, prices: dict[str, Decimal]) -> None:
        for key in self._order:
            raw = self._group_totals.get(key, 0)
            if raw <= 0:
                continue
            label = self._group_label[key]
            amount_str = format_amount(raw, self._group_decimals[key])
            amount = Decimal(amount_str)
            unit = usd_unit_price(label, prices)
            usd = amount * unit
            usd_str = format_usd_value(usd)
            print(f"{label}: {amount_str} ({usd_str}$)", flush=True)


def print_addresses(specs: list[AddrSpec], sol_addr: str) -> None:
    eth_addr = next((s.address for s in specs if s.network == "ethereum"), "")
    tron_addr = next((s.address for s in specs if s.network == "tron"), "")

    print(f"evm: {eth_addr}")
    print(f"tron: {tron_addr}")
    print(f"solana: {sol_addr}")

    seen: set[str] = set()
    for spec in specs:
        if spec.network in ("ethereum", "tron"):
            continue
        key = f"{spec.network}:{spec.variant}:{spec.address}"
        if key in seen:
            continue
        seen.add(key)
        print(f"{spec.network} {spec.variant}: {spec.address}")


def _evm_raw(body: Any) -> int:
    if not isinstance(body, dict):
        raise RuntimeError(f"не JSON-объект от RPC: {body!r}")
    if body.get("error"):
        err = body["error"]
        if _rpc_retryable(err):
            raise _Retryable(str(err))
        raise RuntimeError(str(err))
    hex_bal = body.get("result") or "0x0"
    if not isinstance(hex_bal, str):
        raise RuntimeError(f"неожиданный result: {hex_bal!r}")
    return int(hex_bal, 16)


async def _check_once(session: aiohttp.ClientSession, task: CheckTask) -> int:
    timeout = _request_timeout(task.kind)
    if task.kind in ("evm", "evm_erc20"):
        async with session.post(task.url, json=task.payload, timeout=timeout) as resp:
            await _raise_if_retryable(resp)
            if resp.status >= 400:
                detail = (await resp.text())[:180]
                raise RuntimeError(f"HTTP {resp.status}: {detail}")
            return _evm_raw(await _read_json(resp, task.url))
    if task.kind == "blockcypher":
        async with session.get(task.url, timeout=timeout) as resp:
            await _raise_if_retryable(resp)
            if resp.status == 404:
                return 0
            if resp.status >= 400:
                detail = (await resp.text())[:180]
                raise RuntimeError(f"HTTP {resp.status}: {detail}")
            data = await _read_json(resp, task.url)
            return int((data or {}).get("balance", 0) or 0)
    if task.kind == "utxo_api":
        async with session.get(task.url, timeout=timeout) as resp:
            await _raise_if_retryable(resp)
            if resp.status == 404:
                return 0
            if resp.status >= 400:
                detail = (await resp.text())[:180]
                raise RuntimeError(f"HTTP {resp.status}: {detail}")
            return parse_utxo_balance(await _read_json(resp, task.url))
    if task.kind == "tron_api":
        return parse_tron_balance(await fetch_tron_account(session, task.url))
    if task.kind == "tron_trc20":
        data = await fetch_tron_account(session, task.url)
        return parse_tron_trc20_balance(data, task.variant)
    if task.kind == "blockchair_bch":
        async with session.get(task.url, timeout=timeout) as resp:
            await _raise_if_retryable(resp)
            if resp.status == 404:
                return 0
            if resp.status >= 400:
                detail = (await resp.text())[:180]
                raise RuntimeError(f"HTTP {resp.status}: {detail}")
            return parse_blockchair_bch_balance(await _read_json(resp, task.url), task.address)
    if task.kind == "sol_native":
        async with session.post(task.url, json=task.payload, timeout=timeout) as resp:
            await _raise_if_retryable(resp)
            body = await _read_json(resp, task.url)
            if isinstance(body, dict) and body.get("error") and _rpc_retryable(body["error"]):
                raise _Retryable(str(body["error"]))
            if not isinstance(body, dict):
                raise RuntimeError(f"solana: {body!r}")
            return parse_sol_native_balance(body)
    if task.kind == "sol_spl":
        async with session.post(task.url, json=task.payload, timeout=timeout) as resp:
            await _raise_if_retryable(resp)
            body = await _read_json(resp, task.url)
            if isinstance(body, dict) and body.get("error") and _rpc_retryable(body["error"]):
                raise _Retryable(str(body["error"]))
            if not isinstance(body, dict):
                raise RuntimeError(f"solana spl: {body!r}")
            return parse_sol_spl_balance(body)
    raise RuntimeError(f"unknown kind {task.kind}")


async def run_check(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    host_sems: dict[str, asyncio.Semaphore],
    task: CheckTask,
) -> tuple[CheckTask, int, str | None]:
    host = urlsplit(task.url).netloc or task.url
    host_sem = host_sems.setdefault(host, asyncio.Semaphore(_HOST_CONCURRENCY))
    last_err = "неизвестная ошибка"
    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with sem:
                async with host_sem:
                    raw = await _check_once(session, task)
            return task, raw, None
        except _Retryable as exc:
            last_err = str(exc)
            delay = exc.retry_after
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as exc:
            last_err = str(exc) or exc.__class__.__name__
            delay = None
        except Exception as exc:
            return task, 0, str(exc) or exc.__class__.__name__
        if attempt + 1 >= _MAX_ATTEMPTS:
            break
        await asyncio.sleep(delay if delay is not None else min(8.0, 0.4 * (2 ** attempt)))
    return task, 0, last_err


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


async def main_async(priv_hex: str, concurrency: int) -> int:
    global _tron_lock
    _tron_account_cache.clear()
    _tron_lock = asyncio.Lock()
    specs = collect_addresses(priv_hex)
    sol_addr = solana_address_from_priv(priv_hex)
    print_addresses(specs, sol_addr)
    print("==========")

    tasks = build_tasks(specs, priv_hex)
    sink = BalanceSink(tasks)
    sem = asyncio.Semaphore(concurrency)
    host_sems: dict[str, asyncio.Semaphore] = {}
    connector = aiohttp.TCPConnector(
        limit=max(concurrency * 2, 8),
        ssl=_ssl_context(),
        ttl_dns_cache=300,
    )
    timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=25)
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers=headers,
        trust_env=True,
    ) as session:
        price_task = asyncio.create_task(fetch_usd_prices(session))
        pending = [asyncio.create_task(run_check(session, sem, host_sems, t)) for t in tasks]
        for coro in asyncio.as_completed(pending):
            task, raw, err = await coro
            sink.ingest(task, raw, err)
        prices = await price_task

    sink.print_positive(prices)
    sink.report_errors()
    return 0


def _configure_runtime() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.platform == "win32":
        policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
        if policy is not None:
            asyncio.set_event_loop_policy(policy())


def main() -> int:
    _configure_runtime()
    parser = argparse.ArgumentParser(
        description="Балансы из приватного ключа (адреса + только >0)",
        epilog=f"Разработчик: {DEVELOPER}\n{DEVELOPER_LINKS}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("private_key", help="hex приватный ключ (64 символа)")
    parser.add_argument("-j", "--jobs", type=int, default=12, help="параллельных запросов к RPC/API")
    parser.add_argument("--json", action="store_true", help="отладочный JSON адресов")
    args = parser.parse_args()

    try:
        priv = normalize_privkey_hex(args.private_key)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    if sys.version_info < (3, 10):
        print("Нужен Python 3.10 или новее.", file=sys.stderr)
        return 2

    if args.json:
        for spec in collect_addresses(priv):
            print(
                json.dumps(
                    {
                        "type": "address",
                        "network": spec.network,
                        "variant": spec.variant,
                        "address": spec.address,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        return 0

    try:
        return asyncio.run(main_async(priv, max(1, args.jobs)))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())