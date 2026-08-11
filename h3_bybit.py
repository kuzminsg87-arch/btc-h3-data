#!/usr/bin/env python3

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASES = [
    "https://api.bybit.com",
    "https://api.bytick.com",
]

SYMBOL = "BTCUSDT"
CATEGORY = "linear"


def get(path, params):
    last_error = None

    for base in BASES:
        try:
            url = base + path + "?" + urllib.parse.urlencode(params)

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "H3-v3",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read())

            if data.get("retCode") != 0:
                raise RuntimeError(data.get("retMsg", "Bybit API error"))

            return data["result"]

        except Exception as e:
            last_error = e

    raise RuntimeError(str(last_error))


def ema(values, n):
    a = 2 / (n + 1)
    result = [values[0]]

    for x in values[1:]:
        result.append(a * x + (1 - a) * result[-1])

    return result


def candles(interval):
    data = get(
        "/v5/market/kline",
        {
            "category": CATEGORY,
            "symbol": SYMBOL,
            "interval": interval,
            "limit": 250,
        },
    )["list"]

    rows = [
        {
            "ts": int(r[0]),
            "o": float(r[1]),
            "h": float(r[2]),
            "l": float(r[3]),
            "c": float(r[4]),
            "v": float(r[5]),
        }
        for r in reversed(data)
    ]

    ms = {
        "60": 3600000,
        "240": 14400000,
    }[interval]

    now = int(datetime.now(timezone.utc).timestamp() * 1000)

    rows = [r for r in rows if r["ts"] + ms <= now]

    closes = [r["c"] for r in rows]

    ema5 = ema(closes, 5)[-1]
    ema10 = ema(closes, 10)[-1]
    ema20 = ema(closes, 20)[-1]

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)

    macd = [a - b for a, b in zip(ema12, ema26)]
    signal = ema(macd, 9)

    macd_value = macd[-1]
    signal_value = signal[-1]
    hist = macd_value - signal_value

    tr = [
        max(
            rows[i]["h"] - rows[i]["l"],
            abs(rows[i]["h"] - rows[i - 1]["c"]),
            abs(rows[i]["l"] - rows[i - 1]["c"]),
        )
        for i in range(1, len(rows))
    ]

    atr14 = sum(tr[-14:]) / 14

    avg20 = sum(r["v"] for r in rows[-21:-1]) / 20
    rvol = rows[-1]["v"] / avg20

    return {
        "close": rows[-1]["c"],
        "EMA5": ema5,
        "EMA10": ema10,
        "EMA20": ema20,
        "MACD": macd_value,
        "MACD_signal": signal_value,
        "MACD_hist": hist,
        "ATR14": atr14,
        "volume": rows[-1]["v"],
        "RVOL20": rvol,
        "high20": max(r["h"] for r in rows[-20:]),
        "low20": min(r["l"] for r in rows[-20:]),
    }


def ticker():
    x = get(
        "/v5/market/tickers",
        {
            "category": CATEGORY,
            "symbol": SYMBOL,
        },
    )["list"][0]

    return {
        k: float(x[k])
        for k in [
            "lastPrice",
            "markPrice",
            "indexPrice",
            "fundingRate",
            "openInterest",
        ]
    }


def oi(period):
    data = list(
        reversed(
            get(
                "/v5/market/open-interest",
                {
                    "category": CATEGORY,
                    "symbol": SYMBOL,
                    "intervalTime": period,
                    "limit": 24,
                },
            )["list"]
        )
    )

    previous = float(data[-2]["openInterest"])
    latest = float(data[-1]["openInterest"])

    return {
        "previous": previous,
        "latest": latest,
        "change_pct": (latest / previous - 1) * 100,
    }


def ls(period):
    x = get(
        "/v5/market/account-ratio",
        {
            "category": CATEGORY,
            "symbol": SYMBOL,
            "period": period,
            "limit": 1,
        },
    )["list"][0]

    long_ratio = float(x["buyRatio"])
    short_ratio = float(x["sellRatio"])

    return {
        "long": long_ratio,
        "short": short_ratio,
        "L_S": long_ratio / short_ratio if short_ratio else None,
    }


def main():

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "venue": "Bybit",
        "symbol": SYMBOL,
    }

    integrity = {}

    jobs = {
        "ticker": ticker,
        "1H": lambda: candles("60"),
        "4H": lambda: candles("240"),
        "OI_1H": lambda: oi("1h"),
        "OI_4H": lambda: oi("4h"),
        "LS_1H": lambda: ls("1h"),
        "LS_4H": lambda: ls("4h"),
    }

    for name, function in jobs.items():

        try:
            output[name] = function()
            integrity[name] = True

        except Exception as error:

            output[name] = {
                "error": str(error)
            }

            integrity[name] = False

    output["CoinGlass_Heatmap"] = {
        "available": False,
        "note": "user screenshot recommended",
    }

    integrity["CoinGlass_Heatmap"] = False

    output["data_integrity"] = integrity

    print(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
