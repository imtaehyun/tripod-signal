#!/usr/bin/env python3
"""Telegram notification — sent on EVERY run, including quiet days and failures.

The point is not convenience, it is that **a silent failure and a quiet day look
identical**. If the only message is "go trade", then a broken fetch, an expired
provider endpoint, or a cancelled cron all present as "nothing to do today", and
the strategy quietly stops running while the dashboard shows a stale number. So
every outcome sends exactly one message, and the message always says which
session it is talking about.

Three outcomes:
    trade    the rule wants an order placed        -> loud, with the orders
    quiet    the rule ran, nothing to do           -> one short line
    failed   the run broke before producing a signal -> loud, with the step name

Zero third-party dependencies, same reason as fetch.py: this has to keep working
in Actions years from now.

Secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
Exits non-zero if the send fails, so a broken notifier surfaces as a red run
(and Actions' own failure email) rather than as silence.
"""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.parse
import urllib.request

# Reuse fetch.py's CA bundle resolution. Plain Python on macOS, and any machine
# behind a TLS-inspecting corporate proxy, has a trust store that rejects
# api.telegram.org with CERTIFICATE_VERIFY_FAILED. Actions does not need this;
# testing the notifier locally does, and a notifier you cannot test locally is
# one you find out about at 15:45.
from fetch import CTX

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
PAGE = os.environ.get("DASHBOARD_URL", "https://imtaehyun.github.io/tripod-signal/")


def send(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        raise SystemExit("FATAL: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
    body = urllib.parse.urlencode({
        "chat_id": chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30, context=CTX) as resp:
        payload = json.loads(resp.read())
    if not payload.get("ok"):
        raise SystemExit(f"FATAL: telegram rejected the message: {payload}")
    print("telegram: sent")


def _fill_line(prov: dict | None) -> str:
    """One line saying which price the decision used and when to execute."""
    if not prov or not prov.get("usable"):
        return ("⏱ <b>마감 종가</b> 기준 · 체결은 <b>다음 거래일</b>\n"
                "   (지연 비용 MDD ~8pp/배수 · ADR 0005)")
    at = prov.get("taken_at_et", "?")[11:16]
    if prov.get("same_session_fill"):
        return (f"⏱ <b>{at} ET</b> 시세 기준 · <b>지금 바로</b> 시장가로 체결 "
                f"(MOC 마감 15:50)")
    return (f"⏱ {at} ET 시세 기준 · <b>이미 15:58 지남</b> → 오늘 체결 불가, "
            f"<b>다음 거래일</b>에 체결")


def voltarget_msg(s: dict, prov: dict | None) -> tuple[bool, str]:
    L, P, I = s["latest"], s["params"], s["latest"]["inputs"]
    cash = s.get("cash_ticker", "SGOV")   # from params.CASH_TICKER via signal.json
    now, was = L["weight_pct"], L["prev_weight"] * 100
    legs = " ".join(
        f"{n}d{'✅' if I['legs'][str(n)] else '⬜️'}" for n in P["ma_lengths"])

    if not L["action_required"]:
        return False, (
            f"😴 <b>변동성 타겟 — 할 일 없음</b>\n"
            f"보유 유지: TQQQ <b>{now:.0f}%</b> / {cash} {L['cash_pct']:.0f}% "
            f"(배수 {L['leverage']:.2f}x)\n"
            f"원시 목표 {I['raw_pct']:.0f}% — 데드밴드 해제선 "
            f"{I['release_down_pct']:.0f}% / {I['release_up_pct']:.0f}%\n"
            f"투표 {I['above']}/{I['of']}  {legs}   실현변동성 {I['rvol_pct']:.1f}%"
        )

    side = "매수" if L["delta"] > 0 else "매도"
    other = "매도" if L["delta"] > 0 else "매수"
    pp = abs(L["delta_pp"])
    return True, (
        f"🔔 <b>변동성 타겟 — 리밸런싱</b>\n"
        f"TQQQ <b>{was:.0f}% → {now:.0f}%</b>  ({cash} {L['cash_pct']:.0f}%, "
        f"배수 {L['leverage']:.2f}x)\n\n"
        f"<b>주문</b>\n"
        f"1. TQQQ <b>{pp:.0f}pp {side}</b>\n"
        f"2. {cash} <b>{pp:.0f}pp {other}</b>  (현금 다리는 {cash}로 유지)\n\n"
        f"<b>근거</b>\n"
        f"투표 {I['above']}/{I['of']} = {I['vote']:.2f}   {legs}\n"
        f"실현변동성 {I['rvol_pct']:.1f}% → 원시 목표 {I['raw_pct']:.0f}% → "
        f"격자·데드밴드 후 <b>{now:.0f}%</b>\n"
        f"목표변동성 {I['target_vol_pct']:.0f}%"
    )


def tripod_msg(s: dict) -> tuple[bool, str]:
    L, G, P = s["latest"], s["gears"], s["params"]
    g = G[L["gear"]]
    if not L["action_required"]:
        return False, (f"😴 <b>트라이팟 — 할 일 없음</b>\n"
                       f"보유 유지: {g['label']} ({g['leverage']}x)")
    prev = G[L["prev_gear"]]
    o = L["orders"]
    lines = [f"🔔 <b>트라이팟 — 기어 변경</b>",
             f"{prev['label']} ({prev['leverage']}x) → "
             f"<b>{g['label']} ({g['leverage']}x)</b>", "", "<b>주문</b>"]
    step = 1
    if o["sell"]:
        lines.append(f"{step}. <b>{', '.join(o['sell'])} 전량 매도</b>"); step += 1
    if o["buy"]:
        tgt = " + ".join(f"{x} {g['weights'][x]*100:.0f}%" for x in o["buy"])
        lines.append(f"{step}. <b>{tgt} 매수</b>"); step += 1
    if o["keep"]:
        lines.append(f"{step}. {', '.join(o['keep'])} 유지")
    lines += ["", "<b>근거</b>",
              f"NDX vs {P['ma_length']}일선 {L['legs']['ma']['dist_pct']:+.2f}%",
              f"VIX {P['vix_ma_length']}일 평균 {L['legs']['vix']['value']:.2f} "
              f"(감속 {P['vix_hot']} / 현금 {P['vix_panic']})",
              f"52주 낙폭 {L['legs']['dd']['value']:.2f}% "
              f"(기준 {P['dd_trigger']*100:.0f}%)"]
    return True, "\n".join(lines)


def build_ok() -> tuple[bool, str]:
    with open(os.path.join(DATA, "signal.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    prov = d.get("provisional")
    S = d["strategies"]
    acted_vt, vt = voltarget_msg(S["voltarget"], prov)
    acted_tp, tp = tripod_msg(S["tripod"])
    session = d["data_range"]["last_session"]
    if prov and prov.get("usable"):
        session = prov["quotes"]["^NDX"]["session"] + " (장중)"
    head = f"📅 <b>{session}</b>\n{_fill_line(prov)}"
    return (acted_vt or acted_tp,
            f"{head}\n\n{vt}\n\n{'─'*22}\n\n{tp}\n\n<a href=\"{PAGE}\">대시보드</a>")


def build_fail() -> str:
    step = os.environ.get("FAILED_STEP", "(알 수 없음)")
    run = os.environ.get("RUN_URL", "")
    tail = os.environ.get("FAIL_DETAIL", "").strip()
    body = (f"❌ <b>신호 생성 실패</b>\n"
            f"실패 단계: <code>{html.escape(step)}</code>\n\n"
            f"<b>오늘 신호가 없다. 조용한 날이 아니다.</b>\n"
            f"직전 신호는 대시보드에 남아 있지만 <b>날짜가 오래됐는지 확인해라.</b>")
    if tail:
        body += f"\n\n<pre>{html.escape(tail[:600])}</pre>"
    if run:
        body += f"\n\n<a href=\"{run}\">실행 로그</a>"
    return body


if __name__ == "__main__":
    if "--fail" in sys.argv:
        send(build_fail())
    else:
        acted, text = build_ok()
        send(text)
        print(f"action_required={acted}")
