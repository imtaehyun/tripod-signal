---
# gstack: design-md-format=spec
name: Nasdaq Leverage Signal
description: A utilitarian instrument panel on plain paper that answers "do I place an order today?" in one second, then shows its working underneath.
colors:
  ground: "#F5F6F7"
  surface: "#FFFFFF"
  text: "#111418"
  text-muted: "#5B6470"
  line: "#DCE0E5"
  line-strong: "#C3C9D1"
  buy: "#D6293B"
  buy-tint: "#FBEAEC"
  sell: "#1F5FD1"
  sell-tint: "#E8EFFB"
  warning: "#B7791F"
  warning-tint: "#FBF1E1"
  error: "#B42318"
  error-tint: "#FCEBE9"
  lev-0: "#E4E7EB"
  lev-15: "#8A939E"
  lev-3: "#2B3138"
  dark-ground: "#0F1216"
  dark-surface: "#161A1F"
  dark-text: "#E8EBEE"
  dark-text-muted: "#98A1AC"
  dark-line: "#262C33"
  dark-line-strong: "#39414B"
  dark-buy: "#F2636F"
  dark-buy-tint: "#3A1D22"
  dark-sell: "#6B98F2"
  dark-sell-tint: "#18253D"
  dark-warning: "#E0A84A"
  dark-warning-tint: "#33270F"
  dark-error: "#F07A6E"
  dark-error-tint: "#3A1A17"
  dark-lev-0: "#232931"
  dark-lev-15: "#6B7480"
  dark-lev-3: "#D5DAE0"
typography:
  display:
    fontFamily: Wanted Sans Variable
    fontWeight: 800
    fontSize: clamp(2.25rem, 1.9rem + 1.5vw, 2.75rem)
    lineHeight: 1.12
    letterSpacing: -0.025em
  heading:
    fontFamily: Pretendard Variable
    fontWeight: 600
    fontSize: 1.125rem
    lineHeight: 1.3
  body:
    fontFamily: Pretendard Variable
    fontWeight: 400
    fontSize: 0.9375rem
    lineHeight: 1.55
  label:
    fontFamily: Pretendard Variable
    fontWeight: 400
    fontSize: 0.75rem
    lineHeight: 1.5
  mono:
    fontFamily: JetBrains Mono
    fontWeight: 500
    fontFeature: tnum
    letterSpacing: -0.01em
rounded:
  sm: 4px
  md: 6px
  lg: 8px
  xl: 12px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
  3xl: 48px
components:
  ticket:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.line-strong}"
    rounded: "{rounded.xl}"
    padding: 22px
  order-row-buy:
    backgroundColor: "{colors.buy-tint}"
    textColor: "{colors.buy}"
    rounded: "{rounded.md}"
  order-row-sell:
    backgroundColor: "{colors.sell-tint}"
    textColor: "{colors.sell}"
    rounded: "{rounded.md}"
  banner-warning:
    backgroundColor: "{colors.warning-tint}"
    textColor: "{colors.warning}"
    rounded: "{rounded.lg}"
  banner-error:
    backgroundColor: "{colors.error-tint}"
    textColor: "{colors.error}"
    rounded: "{rounded.lg}"
  nav-link:
    textColor: "{colors.text-muted}"
  nav-link-active:
    textColor: "{colors.text}"
  segmented-active:
    backgroundColor: "{colors.text}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
  tooltip:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.line-strong}"
    rounded: "{rounded.lg}"
---

# Nasdaq Leverage Signal

## Overview

**Creative North Star:** a utilitarian instrument panel. Type size and whitespace carry
the hierarchy, decoration carries nothing, because the only person using this tool
opens it to make one decision.

**Product context:** a personal, Korean-language daily dashboard for two published
leverage rules (Tripod and Vol Target, see `CONTEXT.md`). Its single user gets a
Telegram alert around 15:45 ET, which is midday Pacific, and opens the page on a phone.

**Mode per surface:**
- Today's ticket: Operate. One answer, read in one second.
- Why / chart / history: Read. Supporting evidence, scanned rather than studied.
- Reference (params, validation, differences): Read, quiet.

**Key characteristics:**
- The first thing visible is the verdict: `주문 없음` or `주문 N건`, prefixed with `오늘`
  only when the order goes into today's close (intraday judgement before 15:50 ET).
- Red and blue appear only where something is bought or sold.
- Leverage reads as ink density, light for cash and dark for 3x.
- One container on the page, the ticket. Everything else is separated by hairlines.
- Nothing scrolls sideways on a 390px phone.

## Colors

**Strategy:** Restrained. Neutrals plus two semantic hues, each with a single meaning.

**Light or dark:** light by default, because the use scene is a phone at midday in
office or daylight light. `prefers-color-scheme: dark` switches to the `dark-*`
tokens; there is no separate toggle in the product.

- `buy` / `sell` follow Korean brokerage convention: red means buy (매수), blue means
  sell (매도). They are reserved for order rows, the side label in history, and the
  chart's up-shift/down-shift markers (an up-shift is a TQQQ buy). Never use them
  for leverage level, regime, or "importance".
- `lev-0` → `lev-15` → `lev-3` is one hue at three densities. It encodes leverage
  as an ordinal value in the Tripod gear bands, the Vol Target weight area and the
  ramp legend. `G15_UP` and `G15_DOWN` hold the same book, so they share `lev-15` and
  differ only by pattern: `G15_DOWN` is a 45° hatch of `lev-15` over `lev-0`.
- `warning` marks stale data and `error` marks a failed run. Both exist so that a
  broken day can never look like a quiet day (see `scripts/notify.py`).
- In dark mode the ramp inverts (`dark-lev-3` is the lightest) so that more leverage
  still reads as more ink against the ground.

## Typography

- **Display: Wanted Sans Variable 800.** Used only for the verdict line and the
  preview's page title. It is a Korean grotesk with firmer, more geometric hangul than
  Pretendard, which separates the answer from the explanation even at a glance.
  Source: `https://cdn.jsdelivr.net/gh/wanteddev/wanted-sans@v1.0.3/packages/wanted-sans/fonts/webfonts/variable/split/WantedSansVariable.min.css` (OFL 1.1).
- **Body/UI: Pretendard Variable 400/600.** Already in use; the best-supported hangul
  UI face. Source: `https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css` (OFL 1.1).
- **Numbers: JetBrains Mono 500/600, tabular.** Prices, percentages, dates, the
  holding line (`TQQQ 65% · SGOV 35%`), and the tooltip values, so digits line up
  in columns. Source: Google Fonts `family=JetBrains+Mono:wght@400;500;600;700` (OFL 1.1).
- **Scale:** display 36px on mobile, 44px on desktop, heading 18px, body 15px, label 12px.
  Adjacent levels differ by more than weight alone.

## Layout

- One column, max width 720px, 20px side padding on mobile.
- Order, top to bottom: header (name + judgement time) → strategy tabs → status
  banner (only when stale/failed) → ticket → why (legs/inputs) → timeline chart →
  recent changes (6) → reference.
- Sections are separated by a 1px `line` hairline and 18–22px of space. Rows inside a
  section are separated by a dashed `line`.
- History is a list of two-line rows (judgement → execution date on line one,
  change + order on line two), never a multi-column table that clips on a phone.
- Reference sections stay expanded but sit last, with a muted 15px heading.

## Elevation & Depth

Flat. Borders and tints do the work. The only shadow in the product is the chart
tooltip (`0 6px 18px -8px rgba(17,20,24,.3)`), because it floats over data.

## Shapes

`xl` (12px) for the ticket, `md` (6px) for order rows and the segmented control,
`lg` (8px) for banners and the tooltip, `sm` (4px) for leg chips. Nested radius is
outer minus gap: order rows sit 22px inside a 12px ticket, so they take 6px.

## Components

**Ticket.** The one bordered container. Contents: meta line (`전략 · 날짜 판정`),
verdict in display type, then either the held book (quiet day) or numbered order rows
(order day), then a hairline and the execution line. The verdict is driven by
`action_required` and the order count, never by a gear or weight change alone
(`CONTEXT.md`).

**Order row.** `번호 · 티커 · 매수|매도 · 수량`. Tinted background by side. The side
word and amount take the side colour; the ticker stays `text`.

**Tabs.** Text tabs, the active one has `text` colour, weight 600 and a 2px `text`
underline. A tab whose strategy wants an order carries a 6px `text`-coloured dot.

**Leg / input rows.** Label left, mono value right, then a zone gauge, then a
12px caption that says what moving left or right does. The gauge is an 8px bar
cut at the rule's thresholds into `lev-0` segments; the segment holding today's
value is `lev-15` and its name below is `text` 600. Above the bar a mono pin
shows today's value; below it, mono tick labels at both ends and at every cut,
then one name per zone saying what happens there (`하락 레짐 / 직전 유지 /
상승 레짐`). Zones follow the current state: Tripod's VIX gauge shows only the
threshold of the current regime. Vol Target's realised vol has no rule
threshold, so its cuts are where today's vote puts the raw target at 100% and
50%; its weight gauge is cut at held ± band (`줄인다 / 유지 / 늘린다`). Vol
Target's four MAs render as chips: filled `text` when the latched leg is on,
outlined when off.

**Timeline chart.**
- Upper panel: NDX close on a log scale (`text`, 1.2px) and its 250-day MA
  (`lev-15`, dotted 1.5/2.5). 18px of headroom top and bottom.
- Tripod also overlays the ETFs it holds: TQQQ (`text-muted`, solid) and QLD
  (`text-muted`, dashed 5/3). Prices that far apart cannot share an axis, so on
  this chart every line is rebased to 100 on the window's first day (log scale,
  labelled gridlines, 100 drawn in `line-strong`), NDX and its MA rebased
  together. Lines are named by end labels in a 46px right gutter, not a legend;
  `TQQQ / QLD` toggles sit next to the range control. QQQ is tooltip-only because
  rebased it is indistinguishable from NDX.
- Lower panel (44px): Vol Target weight as an `lev-15` area; Tripod gears as `lev-*`
  bands. A band is never drawn narrower than 2px, so a one-day gear is visible.
- Change markers sit on the price line: ▲ in `buy` for an increase, ▼ in `sell`
  for a decrease, ◇ outlined in `text` for a regime-only change with no orders.
  Each marker clears the line's local envelope (min/max of the line within ±5px)
  by a 5px gap, ▲ below it and ▼ above it, so the line is never covered.
- Range control: segmented `3개월 / 1년 / 3년`, default `1년`. Month labels on the
  3-month view, year labels otherwise.
- Hover (mouse) or press-and-drag (touch, `touch-action: pan-y` so vertical scroll
  still works) shows a dashed crosshair, a dot on the price, and a tooltip that flips
  sides near the right edge. Tooltip rows: date, NDX close, distance to the 250-day
  MA, then for Vol Target the TQQQ weight, vote (n/4), realised vol, raw target; for
  Tripod the gear (`ko` label), VIX 10-day average, 52-week drawdown, then the
  QQQ/QLD/TQQQ close with its move since the window start. Values come from
  `signal.json` `series`.

**Banners.** Stale data (`warning`) and failed run (`error`) sit above the ticket and
state plainly that this is not a quiet day.

**States.** Every interactive element has a visible `:focus-visible` ring (2px `text`).
Loading shows `불러오는 중…` in `text-muted`; a missing signal shows the error banner,
never an empty ticket.

## Do's and Don'ts

- Do: make the verdict the largest text on the page, and the first thing below the tabs.
- Do: use `buy`/`sell` only for an actual buy/sell (order rows, history side, chart markers).
- Do: show leverage as `lev-*` density, with the hatch for `G15_DOWN`.
- Do: keep every row readable at 390px without horizontal scrolling.
- Do: show stale/failed state above the ticket, before any number.
- Don't: colour the ticket, a top bar, or the holding line by leverage. That is what made a
  quiet day look like an alert.
- Don't: put a card inside a section, or lay out three equal-weight cards in a row.
- Don't: use red/amber/blue/grey as gear colours again.
- Don't: show "지금 바로 시장가" or any execution instruction on a day with no orders.
- Don't: let a chart marker overlap the price line.

## Motion

- **Approach:** minimal-functional.
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** theme/tab change 150ms; nothing else animates.
- **The one authored moment:** none. The verdict should be static and immediate.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-05 | Initial design system created | /design-consultation from product context (no competitive research). Memorable thing: know in one second whether there is an order today. |
| 2026-10-05 | Light default, dark by system setting | Use scene is a phone at midday. |
| 2026-10-05 | Leverage as ink density, red/blue reserved for buy/sell | Frees the semantic hues; the old red hero bar read as an alarm on quiet days. |
| 2026-10-05 | No inverted ticket on order days; reference stays expanded | User declined both risks; order days are signalled by the verdict text and tinted order rows. |
| 2026-10-05 | Chart hover tooltip, 3M/1Y/3Y range, coloured markers on the price line with a gap | User feedback on the preview: short changes were hard to read. |
| 2026-10-05 | Input gauges cut into named zones at the rule's thresholds | Ticks alone did not say what left/right meant. |
| 2026-10-05 | Tripod chart overlays TQQQ/QLD rebased to 100 | User wanted to see the held ETFs; rebasing is the only honest shared axis. Display only, no returns computed. |
