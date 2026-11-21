"""Week-one trophy rarity forecast for Grand Theft Auto VI (PS5) on Exophase.

Reads one case (every read the house made of the game's trophy page before the
checkpoint) and writes five quantiles (5/25/50/75/95 %) of every trophy's earn
rate at the case's target. Standard library only, no network, deterministic.

The idea in one paragraph
-------------------------
Exophase shows, for each trophy, the share of the players it tracks who hold
it. Two days after launch the page is early in a long game: 18 % of 54,144
tracked players had finished Chapter 1, 3.6 % Chapter 2 and only a few dozen
early-copy players anything later, and a second tracker with 91,204 owners
showed the same picture within a point. So the page is not badly behind real
play; players simply have a weekend and three more days of playing ahead of
them, and persistence is a poor median for almost every trophy.

The story trophies turn out to follow one curve at different speeds. Chapter 2
stood at 1.71 % and 3.61 % at 39.6 h and 50.2 h after launch and climbed as
steeply (in logit against log time) as Chapter 1 would have at half those
hours, and "Trust" tracks Chapter 1 at about 1/1.5 of the clock. Reading
rate_k(t) = rate_1(t / c_k) puts Chapter 1 a little under 50 % a week in,
Chapter 2 over a quarter, and the long third chapter (c about 6) near 5 %; side trophies that
are earned inside story missions keep their ratio to the chapter they sit in.

Three views of each trophy's rate at the target are blended on the logit scale:

  P  a typed prior for the displayed rate a week after launch (PRIOR below),
     reasoned trophy by trophy from what the trophy asks for;
  S  the last recorded rate moved by the part of the prior's drift that is
     still ahead (so a page that runs ahead of the prior lifts the forecast);
  A  a damped straight-line continuation of the trophy's own last-day trend in
     logit against ln(1 + hours since launch), used only where enough players
     hold the trophy for the trend to be more than rounding noise.

The spread is a normal on the logit scale whose width is the trophy's prior
uncertainty widened by how much the three views disagree. Rates are clamped to
0.01..99.99 like the scorer clamps them, so a trophy expected to stay on the
floor gets quantiles on the floor.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

IN_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

Z_SCORES = (-1.645, -0.674, 0.0, 0.674, 1.645)
LAUNCH = datetime(2026, 11, 19, 0, 0, 0, tzinfo=timezone.utc)

# Hours after LAUNCH of the read the SNAP column below was taken at
# (2026-11-21 about 02:10 UTC, 54,144 players tracked, 85,479 trophies earned;
# the read before it, 39.6 h after launch, had 44,161 and 60,923).
SNAP_HOURS = 50.2
# Hours after LAUNCH the PRIOR column speaks about (2026-11-26 00:00 UTC).
PRIOR_HOURS = 168.0

# How much of a measured last-day trend is carried forward. Catch-up curves
# flatten on the logit scale as they rise, so less than all of it.
TREND_DAMP = 0.7
TREND_MIN = -0.3
TREND_MAX = 4.0
# A trend counts only when this many tracked players hold the trophy now, and
# this many did at the earlier read: below that, 2-decimal rounding dominates.
TREND_HOLDERS_NOW = 40.0
TREND_HOLDERS_THEN = 12.0
# The earlier read of a trend is the newest one at least this many hours old.
TREND_LOOKBACK_HOURS = 18.0

# Blend weights (prior, shifted, trend) with and without a usable trend.
W_WITH_TREND = (0.30, 0.38, 0.32)
W_NO_TREND = (0.50, 0.50, 0.0)

# Disagreement between the views widens the spread by this share of its size.
DISAGREE_GAIN = 0.45
# No median above this: no trophy but the opening mission's is near-universal.
MEDIAN_CAP = 93.0

# Launch night: before Exophase's first refresh the page tracked a few hundred
# early profiles. The rules say the first refresh took it from 638 to 3,868
# players and lowered every rate but the 100 % one, and that persistence then
# missed by about 1.5 logits on average. Below this many tracked players the
# page is still in that state, and a refresh is expected to dilute it.
EARLY_PLAYERS = 2000
EARLY_SHIFT = -1.45
EARLY_SIGMA = 0.5

# name key -> (SNAP: rate on the page 50.2 h after launch,
#              PRIOR: median displayed rate 168 h after launch,
#              SIGMA: logit-scale uncertainty of that prior)
#
# How the priors were reasoned. Chapter 1's own curve, pieced together from its
# two reads and from Chapter 2 read at twice the clock, runs about 1.7 % at
# 20 h, 3.6 % at 25 h, 12 % at 40 h and 18 % at 50 h, its slope in logit against
# log time falling from 3.3 to 2.0 on the way. Carried on with a slope that
# keeps falling, it is near 32 % at 84 h and 48 % at 168 h; the weekend argues
# for a little more and late joiners for a little less. Every story trophy is
# then read off that curve at 168 h / c: Trust c 1.5, Chapter 2 c 2, the Cartel
# Heist and Chapter 3 c about 6 (38 holders at the snapshot against Chapter 2's
# 1,955), and the missions after it further down the steep early part of the
# curve, where a wide spread is the honest answer: nobody but about 16
# early-copy players had finished any of them at the snapshot.
# Side trophies: the ones earned inside missions keep their ratio to Chapter 2
# (bowling 0.7, the UFO scene 0.4, the 4-star escape 0.18); cumulative ones
# (100 vehicles, $100,000 spent) rise with hours played like Chapter 2; early
# optional ones (fishing, an arcade game, the tank, the airport) rise slowly
# along their own measured trend; side-strand finales and heists that only
# open late sit near the late story; completion grinds (250 stunts, 100 photo
# spots, every meditation spot, 100 %) stay on the 0.01 floor.
PRIOR = {
    # platinum and 100 %
    "vicegotaprice": (0.01, 0.01, 0.8),
    "alongroad": (0.01, 0.01, 0.8),
    # story chain
    "justlikeparadise": (100.0, 100.0, 0.0),
    "paradiselost": (18.02, 47.0, 0.55),
    "trust": (7.98, 35.0, 0.7),
    "tsassdrugmoney": (3.61, 27.0, 0.75),
    "breakthebank": (0.07, 6.0, 1.15),
    "vicecitybaby": (0.07, 5.5, 1.15),
    "familymatters": (0.03, 3.0, 1.25),
    "dwnfall": (0.03, 2.4, 1.25),
    "topoftheworldma": (0.03, 2.0, 1.25),
    "hijacked": (0.03, 1.5, 1.3),
    "snowstorm": (0.03, 1.2, 1.3),
    "yougottaknowwhentogetoff": (0.03, 1.0, 1.3),
    # early optional and "falls out of play" trophies
    "baitedmytackle": (16.73, 29.0, 0.45),
    "stickfiddler": (1.84, 4.5, 0.6),
    "whipitgood": (3.25, 21.0, 0.8),
    "letsgobowling": (2.44, 16.0, 0.8),
    "thetruthisoutthere": (1.41, 9.0, 0.85),
    "hottogether": (0.65, 5.0, 0.9),
    "catchmeifyoucan": (0.29, 0.8, 0.8),
    "challengingtank": (0.24, 0.6, 0.8),
    "inthebeginning": (0.21, 0.55, 0.8),
    "gunslinger": (0.11, 0.5, 1.0),
    "tenpin": (0.10, 0.5, 1.0),
    "retailtherapy": (0.09, 0.8, 1.0),
    "sneakthief": (0.10, 1.0, 1.0),
    "treatyoself": (0.13, 2.5, 1.1),
    "thegoodtimestate": (0.05, 0.25, 1.0),
    # side strands and heists that open late
    "thiswasnoboataccident": (0.06, 1.0, 1.2),
    "roadtorehabilitation": (0.02, 0.35, 1.3),
    "thelonerider": (0.02, 0.35, 1.3),
    "supplydemand": (0.01, 0.25, 1.3),
    "spinonthis": (0.01, 0.25, 1.3),
    "aclassicblitzplay": (0.01, 0.3, 1.3),
    "capitaloffense": (0.02, 0.25, 1.3),
    "personalbest": (0.02, 0.2, 1.3),
    "badluckiguess": (0.01, 0.15, 1.3),
    "onthespot": (0.01, 0.25, 1.3),
    "fairgame": (0.01, 0.2, 1.3),
    "theshootist": (0.03, 0.2, 1.2),
    "dimeonthedollar": (0.01, 0.12, 1.3),
    "masterofnone": (0.01, 0.12, 1.3),
    "actionsspeaklouder": (0.01, 0.08, 1.3),
    "littleboxes": (0.01, 0.08, 1.3),
    "maximumwithdrawal": (0.01, 0.06, 1.3),
    "earncashnotkudos": (0.01, 0.06, 1.3),
    "strangersfreaks": (0.01, 0.06, 1.2),
    "positivementalattitude": (0.01, 0.05, 1.2),
    "pestcontrol": (0.01, 0.04, 1.2),
    # completion grinds
    "onelastthing": (0.01, 0.03, 1.1),
    "donttouchmydeck": (0.01, 0.03, 1.1),
    "topfun": (0.01, 0.03, 1.1),
    "youwainker": (0.01, 0.015, 1.0),
    "cunningstunts": (0.01, 0.012, 1.0),
}

# Story order: a later link cannot be more common than an earlier one.
STORY_CHAIN = ("paradiselost", "tsassdrugmoney", "vicecitybaby", "topoftheworldma", "yougottaknowwhentogetoff")


def clamp(pct):
    return min(99.99, max(0.01, pct))


def logit(pct):
    p = clamp(pct) / 100.0
    return math.log(p / (1.0 - p))


def inv_logit(x):
    if x > 40:
        return 100.0
    if x < -40:
        return 0.0
    return 100.0 / (1.0 + math.exp(-x))


def name_key(name):
    """A trophy's name reduced to its ASCII letters and digits, lower case."""
    return "".join(ch for ch in str(name).lower() if ch.isascii() and ch.isalnum())


def hours_after_launch(stamp):
    text = str(stamp).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    when = datetime.fromisoformat(text)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (when - LAUNCH).total_seconds() / 3600.0


def log_time(hours):
    return math.log(1.0 + max(0.0, hours))


def tidy(q):
    """Five quantiles made valid: inside 0..100, 4 decimals, non-decreasing."""
    out = []
    low = 0.0
    for value in q:
        if not math.isfinite(value):
            value = low
        value = round(min(100.0, max(0.0, value)), 4)
        value = max(value, low)
        out.append(int(value) if float(value).is_integer() else value)
        low = value
    return out


def reads_of(case):
    """The case's reads as (hours after launch, players tracked, rates), oldest first."""
    reads = []
    for read in case.get("history") or []:
        rates = read.get("rates")
        if not isinstance(rates, list):
            continue
        try:
            hours = hours_after_launch(read.get("at") or read.get("slot"))
        except (TypeError, ValueError):
            continue
        players = read.get("players_tracked")
        players = float(players) if isinstance(players, (int, float)) else 0.0
        reads.append((hours, players, rates))
    reads.sort(key=lambda r: r[0])
    return reads


def rate_at(read, index):
    rates = read[2]
    if index < len(rates) and isinstance(rates[index], (int, float)):
        return float(rates[index])
    return None


def forecast_case(case):
    trophies = case["trophies"]
    reads = reads_of(case)
    last = reads[-1] if reads else None
    target_hours = hours_after_launch(case["target"])
    last_hours = last[0] if last else hours_after_launch(case["at"])
    ahead = max(0.0, log_time(target_hours) - log_time(last_hours))
    # The share of the prior's snapshot-to-day-7 drift that is still ahead.
    prior_span = log_time(PRIOR_HOURS) - log_time(SNAP_HOURS)
    share_ahead = min(1.25, ahead / prior_span)

    earlier = None
    if last:
        for read in reads:
            if read[0] <= last_hours - TREND_LOOKBACK_HOURS:
                earlier = read
    early_page = bool(last) and last[1] < EARLY_PLAYERS

    medians = {}
    sigmas = {}
    keys = {}
    for index, trophy in enumerate(trophies):
        tid = trophy["id"]
        key = name_key(trophy.get("name", ""))
        keys[tid] = key
        now = rate_at(last, index) if last else None
        known = PRIOR.get(key)

        if early_page:
            # Launch night: expect the first refresh to dilute everything.
            base = now if now is not None else 0.01
            if base >= 99.9:
                medians[tid], sigmas[tid] = 100.0, 0.0
            else:
                medians[tid], sigmas[tid] = inv_logit(logit(base) + EARLY_SHIFT), EARLY_SIGMA
            continue

        if now is None:
            now = known[0] if known else 0.01
        if now >= 99.9:
            medians[tid], sigmas[tid] = 100.0, 0.0
            continue

        level = logit(now)
        if known:
            snap, prior, sigma = known
            view_p = logit(prior)
            drift = view_p - logit(snap)
        else:
            # A trophy the table does not know (the list changed): a modest
            # catch-up from wherever it stands, with a wide spread.
            sigma = 1.3
            drift = 1.4
            view_p = level + drift * share_ahead
        view_s = level + drift * share_ahead

        view_a = None
        if earlier is not None:
            then = rate_at(earlier, index)
            span = log_time(last_hours) - log_time(earlier[0])
            if then is not None and span > 0.05:
                holders_now = now * last[1] / 100.0
                holders_then = then * earlier[1] / 100.0
                if holders_now >= TREND_HOLDERS_NOW and holders_then >= TREND_HOLDERS_THEN:
                    slope = (level - logit(then)) / span
                    slope = min(TREND_MAX, max(TREND_MIN, slope))
                    view_a = level + TREND_DAMP * slope * ahead

        if view_a is None:
            w_p, w_s, w_a = W_NO_TREND
            views = (view_p, view_s)
            centre = w_p * view_p + w_s * view_s
        else:
            w_p, w_s, w_a = W_WITH_TREND
            views = (view_p, view_s, view_a)
            centre = w_p * view_p + w_s * view_s + w_a * view_a
        disagreement = max(views) - min(views)
        # Uncertainty shrinks with the horizon, but never below a floor.
        horizon_scale = max(0.35, min(1.0, math.sqrt(share_ahead / 0.72))) if share_ahead > 0 else 0.35
        spread = math.sqrt((sigma * horizon_scale) ** 2 + (DISAGREE_GAIN * disagreement) ** 2)
        medians[tid] = min(MEDIAN_CAP, inv_logit(centre))
        sigmas[tid] = spread

    # The story chain: a later chapter is never more common than an earlier one.
    by_key = {key: tid for tid, key in keys.items()}
    ceiling = None
    for key in STORY_CHAIN:
        tid = by_key.get(key)
        if tid is None or tid not in medians:
            continue
        if ceiling is not None and medians[tid] > ceiling:
            medians[tid] = ceiling
        ceiling = medians[tid]

    rows = []
    for trophy in trophies:
        tid = trophy["id"]
        median = medians[tid]
        sigma = sigmas[tid]
        if median >= 99.995:
            q = [99.99, 100.0, 100.0, 100.0, 100.0]
        else:
            centre = logit(median)
            q = [clamp(inv_logit(centre + z * sigma)) for z in Z_SCORES]
        rows.append({"id": tid, "q": tidy(q)})
    return {"trophies": rows}


def fallback_case(case):
    """If anything above fails on a case: its last rates, widened, still valid."""
    reads = reads_of(case)
    rows = []
    for index, trophy in enumerate(case["trophies"]):
        now = rate_at(reads[-1], index) if reads else None
        centre = logit(now if now is not None else 0.01)
        q = [clamp(inv_logit(centre + z * 1.2)) for z in Z_SCORES]
        rows.append({"id": trophy["id"], "q": tidy(q)})
    return {"trophies": rows}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(IN_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        try:
            result = forecast_case(case)
        except Exception:
            result = fallback_case(case)
        text = json.dumps(result, separators=(",", ":")) + "\n"
        (OUT_DIR / (path.stem + ".out")).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
