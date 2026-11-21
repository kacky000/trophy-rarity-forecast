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
rate_k(t) = rate_1(t / c_k) puts Chapter 1 near 55 % a week in, Chapter 2
near 30 %, and the long third chapter (c about 6) near 5 %; side trophies that
are earned inside story missions keep their ratio to the chapter they sit in.

Three views of each trophy's rate at the target are blended on the logit scale:

  P  a typed prior for the displayed rate a week after launch (PRIOR below),
     reasoned trophy by trophy from what the trophy asks for;
  S  the last recorded rate moved by the part of the prior's drift that is
     still ahead (so a page that runs ahead of the prior lifts the forecast);
  A  a damped straight-line continuation of the trophy's own last-day trend in
     probit against ln(1 + hours since launch), used only where enough players
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
from statistics import NormalDist

NORMAL = NormalDist()

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

# The trend is a straight line of the trophy's probit (normal score) against
# ln(1 + hours since launch). If the hours a player needs to reach a trophy are
# lognormal across players who keep arriving at a steady pace, the rate is a
# normal CDF of log time and that line is exact; the reads agree with it: the
# probit slopes of Chapter 1, Chapter 2, Trust, 100 vehicles, bowling and the
# UFO scene between 39.6 h and 50.2 h were all 1.1-1.35, while their logit
# slopes ran from 2.0 to 3.3 depending on how rare the trophy still was.
# Less than all of the slope is carried forward: some players stop playing,
# and weekdays follow the weekend. Backtested on archived first-weeks of four
# big story launches (Cyberpunk 2077, Elden Ring, Hogwarts Legacy, Red Dead
# Redemption 2; achievement rates from two early reads extended to a later
# one): the logit pinball loss was 0.31-0.37 holding rates flat, 0.15 at
# half the slope and 0.07-0.08 at 0.85-1.0 of it.
TREND_DAMP = 0.9
TREND_MIN = -0.2
TREND_MAX = 1.6
# A trend counts only when this many tracked players hold the trophy now, and
# this many did at the earlier read: below that, 2-decimal rounding dominates.
TREND_HOLDERS_NOW = 40.0
TREND_HOLDERS_THEN = 12.0
# The earlier read of a trend is the newest one at least this many hours old:
# a whole day, so that the hour of the day cancels out of the slope.
TREND_LOOKBACK_HOURS = 24.0

# Blend weights (prior, shifted, trend) with and without a usable trend.
W_WITH_TREND = (0.10, 0.15, 0.75)
W_NO_TREND = (0.50, 0.50, 0.0)

# Disagreement between the views widens the spread by this share of its size.
DISAGREE_GAIN = 0.45
# No median above this: no trophy but the opening mission's is near-universal.
MEDIAN_CAP = 93.0

# Launch night: before Exophase's first refresh the page tracked a few hundred
# early profiles. The rules say the first refresh took it from 638 to 3,868
# players and lowered every rate but the 100 % one. Below EARLY_PLAYERS tracked
# players the page is still in that state. A rate there is a whole number of
# holders over the players tracked (1.10 % of 638 is 7 reviewers), and players
# who started at launch cannot hold a late trophy 90 minutes later, so the
# refreshed rate is those same holders over the refreshed player count, as
# the page prints it; the top quantile allows for one more holder.
EARLY_PLAYERS = 2000
FIRST_REFRESH_PLAYERS = 3868

# name key -> (SNAP: rate on the page 50.2 h after launch,
#              PRIOR: median displayed rate 168 h after launch,
#              SIGMA: logit-scale uncertainty of that prior)
#
# How the priors were reasoned. Chapter 1's own curve, pieced together from its
# two reads and from Chapter 2 read at twice the clock, runs about 1.7 % at
# 20 h, 3.6 % at 25 h, 12 % at 40 h and 18 % at 50 h, its slope in logit against
# log time falling from 3.3 to 2.0 on the way, which is what a normal CDF of
# log time does on its way up from the tail (its probit slope held at 1.1-1.35
# throughout). A probit line of slope 1.0-1.2 carries Chapter 1 to 61-70 % at
# 168 h; players who stop and quieter weekdays argue for less, so the prior
# is 55 %. Chapter 2, Trust and the side trophies tied to them are placed the
# same way, each a little under its own probit line. Every story trophy is
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
    "vicegotaprice": (0.01, 0.01, 0.5),
    "alongroad": (0.01, 0.01, 0.5),
    # story chain
    "justlikeparadise": (100.0, 100.0, 0.0),
    "paradiselost": (18.02, 55.0, 0.6),
    "trust": (7.98, 40.0, 0.7),
    "tsassdrugmoney": (3.61, 30.0, 0.75),
    "breakthebank": (0.07, 6.0, 1.15),
    "vicecitybaby": (0.07, 5.5, 1.15),
    "familymatters": (0.03, 3.0, 1.25),
    "dwnfall": (0.03, 2.4, 1.25),
    "topoftheworldma": (0.03, 2.0, 1.25),
    "hijacked": (0.03, 1.5, 1.3),
    "snowstorm": (0.03, 1.2, 1.3),
    "yougottaknowwhentogetoff": (0.03, 1.0, 1.3),
    # early optional and "falls out of play" trophies
    "baitedmytackle": (16.73, 33.0, 0.5),
    "stickfiddler": (1.84, 5.5, 0.6),
    "whipitgood": (3.25, 23.0, 0.8),
    "letsgobowling": (2.44, 18.0, 0.8),
    "thetruthisoutthere": (1.41, 11.0, 0.85),
    "hottogether": (0.65, 6.5, 0.9),
    "catchmeifyoucan": (0.29, 0.85, 0.8),
    "challengingtank": (0.24, 0.6, 0.8),
    "inthebeginning": (0.21, 0.58, 0.8),
    "gunslinger": (0.11, 0.5, 1.0),
    "tenpin": (0.10, 0.8, 1.0),
    "retailtherapy": (0.09, 1.6, 1.05),
    "sneakthief": (0.10, 2.0, 1.05),
    "treatyoself": (0.13, 5.0, 1.15),
    "thegoodtimestate": (0.05, 0.25, 1.0),
    # side strands and heists that open late
    "thiswasnoboataccident": (0.06, 2.0, 1.2),
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
    "youwainker": (0.01, 0.025, 1.1),
    "cunningstunts": (0.01, 0.02, 1.1),
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


def probit(pct):
    return NORMAL.inv_cdf(clamp(pct) / 100.0)


def inv_probit(z):
    return 100.0 * NORMAL.cdf(z)


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
    """The case's reads as (hours after launch, players tracked, rates, as-of hours), oldest first.

    Exophase refreshes the page's counts in steps, hours apart, so a read can
    repeat the one before it. The as-of hours of a read are the hours of the
    first read that showed the same page: the closest the recording gets to
    the moment the counts were taken.
    """
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
    dated = []
    for read in reads:
        as_of = read[0]
        if dated and dated[-1][1] == read[1] and dated[-1][2] == read[2]:
            as_of = dated[-1][3]
        dated.append((read[0], read[1], read[2], as_of))
    return dated


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
            if read[3] <= last[3] - TREND_LOOKBACK_HOURS:
                earlier = read
    early_page = bool(last) and last[1] < EARLY_PLAYERS

    medians = {}
    sigmas = {}
    fixed = {}
    keys = {}
    for index, trophy in enumerate(trophies):
        tid = trophy["id"]
        key = name_key(trophy.get("name", ""))
        keys[tid] = key
        now = rate_at(last, index) if last else None
        known = PRIOR.get(key)

        if early_page:
            # Launch night: the same holders over the refreshed player count.
            base = now if now is not None else 0.0
            if base >= 99.9:
                medians[tid], sigmas[tid] = 100.0, 0.0
            else:
                holders = round(base * last[1] / 100.0)
                diluted = round(100.0 * holders / FIRST_REFRESH_PLAYERS, 2)
                one_more = round(100.0 * (holders + 1) / FIRST_REFRESH_PLAYERS, 2)
                fixed[tid] = [diluted, diluted, diluted, diluted, one_more]
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
            span = log_time(last[3]) - log_time(earlier[3])
            if then is not None and span > 0.05:
                holders_now = now * last[1] / 100.0
                holders_then = then * earlier[1] / 100.0
                if holders_now >= TREND_HOLDERS_NOW and holders_then >= TREND_HOLDERS_THEN:
                    slope = (probit(now) - probit(then)) / span
                    slope = min(TREND_MAX, max(TREND_MIN, slope))
                    view_a = logit(inv_probit(probit(now) + TREND_DAMP * slope * ahead))

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
        if tid in fixed:
            rows.append({"id": tid, "q": tidy(fixed[tid])})
            continue
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
