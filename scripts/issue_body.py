#!/usr/bin/env python3
"""Write /tmp/<key>.{md,title} for the GitHub issue the settled run opens.

Lifted out of daily.yml so it can be run and read like code instead of being a
heredoc inside YAML. An open `rebalance` issue means a trade that has not been
executed yet; closing it is the record that it was.

The Telegram message (scripts/notify.py) is the thing that actually reaches you
in time to trade. This issue is the durable log.
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")


def tripod(S: dict, out: list[str]) -> str:
    L, G, P = S["tripod"]["latest"], S["tripod"]["gears"], S["tripod"]["params"]
    g, prev = G[L["gear"]], G[L["prev_gear"]]
    legs, o = L["legs"], L["orders"]
    title = (f"Rebalance [tripod]: {L['date']} close -> {g['label']} "
             f"({g['leverage']}x), was {prev['label']}")
    p = out.append
    p(f"**{prev['label']} ({prev['leverage']}x) -> {g['label']} ({g['leverage']}x)**\n")
    p(f"Judged on the **{L['date']}** close. Per the rule, execute on the **next session**.\n")
    p("## Orders\n")
    step = 1
    if o["sell"]:
        p(f"{step}. Sell **100% of {', '.join(o['sell'])}**"); step += 1
    if o["buy"]:
        tgt = " + ".join(f"{x} {g['weights'][x]*100:.0f}%" for x in o["buy"])
        src = "the proceeds" if o["sell"] else "cash on hand"
        p(f"{step}. Buy **{tgt}** with {src}"); step += 1
    if o["keep"]:
        p(f"{step}. Keep **{', '.join(o['keep'])}** as is")
    p("\n## Why\n")
    p("| leg | value | threshold |")
    p("|---|---|---|")
    p(f"| NDX vs {P['ma_length']}d MA | {legs['ma']['dist_pct']:+.2f}% "
      f"| up >+{P['up_band']*100:.0f}% / down <-{P['down_band']*100:.0f}% |")
    p(f"| VIX {P['vix_ma_length']}d avg | {legs['vix']['value']:.2f} "
      f"| de-gear >= {P['vix_hot']} / cash >= {P['vix_panic']} |")
    p(f"| 52w drawdown | {legs['dd']['value']:.2f}% "
      f"| trigger {P['dd_trigger']*100:.0f}% |")
    return title


def voltarget(S: dict, out: list[str]) -> str:
    vt = S["voltarget"]
    L, P, I = vt["latest"], vt["params"], vt["latest"]["inputs"]
    cash = vt.get("cash_ticker", "SGOV")
    was, now = L["prev_weight"] * 100, L["weight_pct"]
    side = "Buy" if L["delta"] > 0 else "Sell"
    other = "Sell" if L["delta"] > 0 else "Buy"
    pp = abs(L["delta_pp"])
    title = f"Rebalance [voltarget]: {L['date']} -> TQQQ {now:.0f}%, was {was:.0f}%"
    p = out.append
    p(f"**TQQQ {was:.0f}% -> {now:.0f}%**  ({cash} {L['cash_pct']:.0f}%, "
      f"account leverage {L['leverage']:.2f}x)\n")
    if L.get("provisional"):
        p(f"Judged on a live **15:45 ET** quote for {L['date']}, so this was placed "
          f"into the **same close**. See ADR 0005.\n")
    else:
        p(f"Judged on the **{L['date']}** close. Execute on the **next session**.\n")
    p("## Orders\n")
    p(f"1. **{side} {pp:.0f}pp of the account in TQQQ**")
    p(f"2. **{other} {pp:.0f}pp of {cash}** — the cash leg is held in {cash}, "
      f"not as uninvested cash (worth 1.99pp of CAGR; see params.py)")
    p(f"\nEnd state: TQQQ {now:.0f}% / {cash} {L['cash_pct']:.0f}%.\n")
    p("## Why\n")
    p("| input | value |")
    p("|---|---|")
    p(f"| trend vote (latched legs) | {I['above']}/{I['of']} = {I['vote']:.2f} |")
    p(f"| realised vol ({'/'.join(str(w) for w in P['vol_windows'])}d avg) | {I['rvol_pct']:.1f}% |")
    p(f"| target vol / (3 x rvol) | {P['target_vol']*100:.0f}% / (3 x {I['rvol_pct']:.1f}%) |")
    p(f"| raw target | {I['raw_pct']:.1f}% |")
    p(f"| after {I['step_pp']:.0f}pp grid + {I['band_pp']:.0f}pp deadband | **{now:.0f}%** |")
    legs = ", ".join(
        f"{n}d {'on' if I['legs'][str(n)] else 'off'} ({I['ma_dist_pct'][str(n)]:+.1f}%)"
        for n in P["ma_lengths"])
    p(f"\nLegs: {legs}. A leg latches on above MA*(1+{P['ma_band']}) and off below "
      f"MA*(1-{P['ma_band']}), carrying its state in between.")
    return title


def main() -> None:
    with open(os.path.join(DATA, "signal.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    S = d["strategies"]
    for key, fn in (("tripod", tripod), ("voltarget", voltarget)):
        if not S[key]["latest"]["action_required"]:
            continue
        body: list[str] = []
        title = fn(S, body)
        body.append("\nClose this issue once the rebalance is actually placed. "
                    "An open issue means a trade you have not executed yet.")
        body.append("\n<sub>Not investment advice. Auto-generated.</sub>")
        with open(f"/tmp/{key}.md", "w", encoding="utf-8") as fh:
            fh.write("\n".join(body))
        with open(f"/tmp/{key}.title", "w", encoding="utf-8") as fh:
            fh.write(title)
        print(f"wrote /tmp/{key}.md")


if __name__ == "__main__":
    main()
