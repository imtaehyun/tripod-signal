#!/usr/bin/env python3
"""Fetch daily closes for ^NDX and ^VIX into append-only CSVs.

Zero third-party dependencies on purpose: this has to still run in GitHub
Actions years from now without a lockfile rotting out from under it.

Source chain (first success wins):
    ndx -> Yahoo query1  -> Yahoo query2
    vix -> CBOE official -> Yahoo query1 -> Yahoo query2

CBOE is primary for VIX because it is the authoritative publisher and its CSV
goes back to 1990-01-02, which is what bounds our usable history.

Usage:
    python scripts/fetch.py            # incremental (default)
    python scripts/fetch.py --full     # re-download full history from scratch
"""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

# Deliberately minimal. Yahoo fingerprints requests: a full Chrome UA string
# that is NOT accompanied by a real Chrome TLS fingerprint gets a blanket 429,
# while a plain generic UA is served normally. Do not "improve" this.
UA = "Mozilla/5.0"

CBOE_VIX = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"


def _ssl_context() -> ssl.SSLContext:
    """Prefer certifi's CA bundle when present.

    Plain Python on macOS (and behind a TLS-inspecting corporate proxy) often
    has an empty trust store, which makes every fetch fail with
    CERTIFICATE_VERIFY_FAILED. GitHub Actions does not need this, but a
    developer running the script locally does.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


CTX = _ssl_context()


def _get(url: str, timeout: int = 60, attempts: int = 4) -> bytes:
    """GET with backoff on the transient failures these providers actually emit.

    Yahoo returns 429 freely when several requests land close together, and it
    clears within seconds. Retrying here is much cheaper than failing over to a
    lower-quality source.
    """
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", "Accept": "*/*"}
    )
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
        except urllib.error.URLError as exc:
            last = exc
        if attempt < attempts - 1:
            delay = 3 * (2 ** attempt)  # 3s, 6s, 12s
            print(f"    retry in {delay}s ({last})")
            time.sleep(delay)
    raise last if last else RuntimeError("unreachable")


Rows = list[tuple[str, float]]


def _dedupe(rows: Rows) -> Rows:
    """Last value wins per date, then sort ascending."""
    seen: dict[str, float] = {}
    for day, close in rows:
        seen[day] = close
    return sorted(seen.items())


def from_yahoo(symbol: str, host: str = "query1") -> Rows:
    url = (
        f"https://{host}.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}"
        "?period1=0&period2=9999999999&interval=1d&includePrePost=false"
    )
    result = json.loads(_get(url))["chart"]["result"][0]
    stamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    out: Rows = []
    for ts, close in zip(stamps, closes):
        if close is None:
            continue
        # Yahoo stamps a daily bar at the exchange open; UTC date is the session date.
        day = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()
        out.append((day.isoformat(), round(float(close), 6)))
    return _dedupe(out)


def from_cboe() -> Rows:
    text = _get(CBOE_VIX).decode("utf-8", "replace")
    out: Rows = []
    for row in csv.DictReader(io.StringIO(text)):
        raw_date = (row.get("DATE") or "").strip()
        raw_close = (row.get("CLOSE") or "").strip()
        if not raw_date or not raw_close:
            continue
        try:
            day = dt.datetime.strptime(raw_date, "%m/%d/%Y").date()
            out.append((day.isoformat(), round(float(raw_close), 6)))
        except ValueError:
            continue
    return _dedupe(out)


SOURCES: dict[str, list[tuple[str, callable]]] = {
    "ndx": [
        ("yahoo:query1", lambda: from_yahoo("^NDX", "query1")),
        ("yahoo:query2", lambda: from_yahoo("^NDX", "query2")),
    ],
    "vix": [
        ("cboe", from_cboe),
        ("yahoo:query1", lambda: from_yahoo("^VIX", "query1")),
        ("yahoo:query2", lambda: from_yahoo("^VIX", "query2")),
    ],
}


def fetch(key: str) -> Rows:
    errors = []
    for name, loader in SOURCES[key]:
        try:
            rows = loader()
            if len(rows) < 250:
                raise RuntimeError(f"only {len(rows)} rows, refusing to trust it")
            print(f"  {key}: {len(rows)} rows from {name} "
                  f"({rows[0][0]} .. {rows[-1][0]})")
            return rows
        except Exception as exc:  # noqa: BLE001 - the fallback chain is the point
            errors.append(f"{name}: {exc}")
    raise SystemExit(f"FATAL: could not fetch {key}. Tried -> " + " | ".join(errors))


def merge_into_csv(key: str, fresh: Rows, full: bool) -> int:
    """Merge fresh rows into data/<key>.csv. Returns the count of new dates.

    Append-only in spirit: an existing date keeps its stored value unless --full
    is passed. A provider silently revising last week's close must not rewrite
    history we already traded on.
    """
    path = os.path.join(DATA, f"{key}.csv")
    existing: dict[str, str] = {}
    if os.path.exists(path) and not full:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                existing[row["date"]] = row["close"]

    added = 0
    for day, close in fresh:
        if day not in existing:
            existing[day] = f"{close:.6f}".rstrip("0").rstrip(".")
            added += 1

    os.makedirs(DATA, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "close"])
        for day in sorted(existing):
            writer.writerow([day, existing[day]])
    return added


def main() -> None:
    full = "--full" in sys.argv
    print(f"fetch: {'FULL rebuild' if full else 'incremental'}")
    total_new = 0
    for key in SOURCES:
        added = merge_into_csv(key, fetch(key), full)
        print(f"  {key}: +{added} new dates")
        total_new += added
    print(f"fetch: {total_new} new dates total")


if __name__ == "__main__":
    main()
