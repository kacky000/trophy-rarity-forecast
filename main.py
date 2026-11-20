"""Week-one trophy rarity forecast for Grand Theft Auto VI (PS5) on Exophase.

Reads one case (every read the house made of the game's trophy page before the
checkpoint) and writes five quantiles (5/25/50/75/95 %) of every trophy's earn
rate at the case's target. Standard library only, no network, deterministic.

The idea in one paragraph
-------------------------
Exophase shows, for each trophy, the share of the players it tracks whose
profile held the trophy *the last time Exophase scanned that profile*. Early in
a launch most tracked profiles were scanned once, minutes after their first
trophy, so the page lags real progress badly: about 40 hours after launch it
showed 1.38 trophies per tracked player while freshly synced profiles on another
tracker averaged about six. Mature Exophase pages of comparable games (a month
after launch) show first-chapter trophies at 55-90 % and story endings near
30 %. So the week-one question is not "do rates drift" but "how far does the
page catch up", and persistence is a poor median for almost every trophy.

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
# (2026-11-20 about 15:35 UTC, 44,161 players tracked, 60,923 trophies earned).
SNAP_HOURS = 39.6
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

# name key -> (SNAP: rate on the page 39.6 h after launch,
#              PRIOR: median displayed rate 168 h after launch,
#              SIGMA: logit-scale uncertainty of that prior)
#
# How the priors were reasoned. At the snapshot, 12 % of tracked players showed
# Chapter 1 and 1.7 % Chapter 2, with the page far behind real play. By day 7
# the weekend has passed and a good share of profiles has been rescanned at
# least once, but new and never-rescanned players still drag every rate down.
# Archived Exophase pages of earlier launches back this up: one platformer's
# page went from 474 tracked players a day and a half after launch to 26,849
# four weeks later while its easiest progress trophy rose from 45 % to 92 %
# (about +2.7 logits), so most of the players on a day-7 page are first scanned
# days into their playthrough. I take the displayed rate to reach roughly half
# of real progress: Chapter 1 about 45 %, falling along the story to about
# 1.6 % for the final mission of a long game. Reviewer accounts (4 platinums, about 9 story completions) put a
# floor of 0.01-0.03 % under many trophies at the snapshot; that floor dilutes
# to nothing as tracked players grow, so late-story and grind trophies are
# priced from real play alone. Optional feats that fall out of ordinary play
# (vehicles discovered, a first arcade game, bowling) grow with hours played;
# completion grinds (250 stunts, 100 photo spots, 100 %) stay on the floor.
PRIOR = {
    # platinum and 100 %
    "vicegotaprice": (0.01, 0.01, 0.9),
    "alongroad": (0.01, 0.01, 0.9),
    # story chain
    "justlikeparadise": (100.0, 100.0, 0.0),
    "paradiselost": (11.98, 45.0, 0.85),
    "trust": (4.26, 32.0, 0.95),
    "tsassdrugmoney": (1.71, 19.0, 1.0),
    "breakthebank": (0.03, 8.0, 1.25),
    "vicecitybaby": (0.03, 7.0, 1.25),
    "familymatters": (0.02, 4.4, 1.3),
    "dwnfall": (0.02, 3.5, 1.3),
    "topoftheworldma": (0.02, 3.0, 1.3),
    "hijacked": (0.02, 2.5, 1.35),
    "snowstorm": (0.02, 1.9, 1.35),
    "yougottaknowwhentogetoff": (0.02, 1.6, 1.35),
    # early optional and "falls out of play" trophies
    "baitedmytackle": (13.30, 24.0, 0.7),
    "stickfiddler": (1.42, 5.0, 0.9),
    "whipitgood": (1.70, 14.0, 1.0),
    "letsgobowling": (1.26, 5.0, 0.95),
    "thetruthisoutthere": (0.72, 3.5, 1.0),
    "hottogether": (0.31, 3.0, 1.05),
    "catchmeifyoucan": (0.23, 1.5, 1.05),
    "challengingtank": (0.20, 1.3, 1.05),
    "inthebeginning": (0.17, 1.2, 1.05),
    "gunslinger": (0.08, 1.2, 1.15),
    "tenpin": (0.06, 0.5, 1.15),
    "retailtherapy": (0.04, 0.5, 1.2),
    "sneakthief": (0.04, 0.5, 1.2),
    "treatyoself": (0.03, 0.6, 1.25),
    "thegoodtimestate": (0.04, 0.2, 1.2),
    # still on the reviewer floor at the snapshot: side strands and heists
    "aclassicblitzplay": (0.01, 0.4, 1.35),
    "capitaloffense": (0.01, 0.25, 1.35),
    "badluckiguess": (0.01, 0.2, 1.35),
    "personalbest": (0.01, 0.15, 1.35),
    "onthespot": (0.01, 0.3, 1.35),
    "dimeonthedollar": (0.01, 0.15, 1.35),
    "masterofnone": (0.01, 0.15, 1.35),
    "fairgame": (0.01, 0.3, 1.35),
    "roadtorehabilitation": (0.01, 0.45, 1.35),
    "thiswasnoboataccident": (0.02, 0.45, 1.35),
    "thelonerider": (0.02, 0.45, 1.35),
    "supplydemand": (0.01, 0.4, 1.35),
    "spinonthis": (0.01, 0.4, 1.35),
    "littleboxes": (0.01, 0.08, 1.3),
    "maximumwithdrawal": (0.01, 0.06, 1.3),
    "actionsspeaklouder": (0.01, 0.05, 1.3),
    "pestcontrol": (0.01, 0.04, 1.3),
    "strangersfreaks": (0.01, 0.05, 1.3),
    "earncashnotkudos": (0.01, 0.05, 1.3),
    "donttouchmydeck": (0.01, 0.05, 1.3),
    "positivementalattitude": (0.01, 0.04, 1.3),
    "onelastthing": (0.01, 0.02, 1.2),
    "topfun": (0.01, 0.02, 1.2),
    "theshootist": (0.01, 0.012, 1.1),
    "youwainker": (0.01, 0.012, 1.1),
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
