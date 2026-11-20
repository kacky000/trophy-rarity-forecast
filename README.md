# trophy-rarity-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/kacky000/trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/kacky000/trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A quantile forecast of every Grand Theft Auto VI (PS5) trophy's earn rate on Exophase at the end of launch week
(2026-11-26 00:00 UTC), made from the reads of the trophy page recorded up to 2026-11-21 11:30 UTC. One Python file,
standard library only, no network, the same bytes on every run.

## What it forecasts and how it is scored

For each of the 55 trophies the program writes five quantiles (5 %, 25 %, 50 %, 75 %, 95 %) of the percent of
Exophase-tracked players who hold it at the target. The score is the mean pinball loss on the logit scale, with rates
clamped to 0.01..99.99, so being a factor of two off on a 0.05 % trophy costs as much as missing 33 % for 50 %, and
honest spreads are rewarded. Everything in the model therefore lives on the logit scale.

## Why not persistence

Exophase's rate is the share of tracked players whose profile held the trophy the last time Exophase scanned it, so in
launch week the page runs well behind real play:

- About 40 hours after launch the page showed 44,161 tracked players holding 60,923 trophies, 1.38 each: 100 % with the
  opening mission, 12 % with Chapter 1, 1.7 % with Chapter 2, and a floor of 0.01-0.03 % under the late story left by
  a handful of pre-launch reviewer accounts (4 platinums).
- Profiles synced within the hour on another tracker at the same moment averaged about six trophies.
- Archived Exophase pages of earlier launches show the catch-up: one page went from 474 tracked players a day and a
  half after launch to 26,849 four weeks later, with its easiest progress trophy going from 45 % to 92 %; month-old
  pages of long story games show first chapters at 55-90 % and endings near 30 %.

So nearly every rate should rise over the four and a half days after the deadline, the story chain by several logits,
while the reviewer floor dilutes away as tracked players multiply and pure grind trophies (100 %, 250 stunts, 100
photo spots) stay at the 0.01 % clamp.

## The model

For each trophy three views of its logit rate at the target are blended:

| view | what it says | weight (trend usable / not) |
| --- | --- | --- |
| P, prior | a typed median for the displayed rate a week after launch, reasoned from what the trophy asks for | 0.30 / 0.50 |
| S, shifted | the last recorded rate plus the share of the prior's drift that is still ahead of the last read | 0.38 / 0.50 |
| A, trend | the trophy's own last-day slope of logit against ln(1 + hours since launch), damped to 70 % and clipped | 0.32 / 0 |

- The trend is used only when at least 40 tracked players hold the trophy now and 12 did at the earlier read; below
  that a 2-decimal page is rounding noise.
- S makes the forecast follow the page: if the recorded rates run ahead of the prior's path the median rises, and if
  the page stalls the median falls.
- The spread is a normal on the logit scale: the trophy's prior uncertainty (0.7 for early optional trophies, 0.85-1.0
  for the first chapters, 1.25-1.35 for late story and floor trophies) combined with 45 % of the gap between the most
  and least optimistic view.
- Story chapters are kept in order (a later chapter is never forecast above an earlier one), no median exceeds 93 %
  except the opening mission's, which has read 100.00 % in every read and is forecast to stay there.
- Quantiles are clamped to 0.01..99.99 like the scorer's logit, so floor trophies get quantiles on the floor.
- On launch night (fewer than 2,000 tracked players, the practice cases) the page is the pre-refresh one; the rules
  describe the first refresh as a sixfold jump in tracked players that lowered every rate, so the forecast there is a
  dilution of about 1.45 logits with a spread of 0.5.
- A trophy the table does not know (if the list changes) gets a modest catch-up and a wide spread; any failure inside
  a case falls back to a wide band around its last rates, so the output is always valid.

The priors, the snapshot they start from and the reasoning behind each group are in the `PRIOR` table in `main.py`.

## How sure this is

Not very, and the spreads say so: the 5-95 % band for Chapter 1 runs from roughly 15 % to 80 %. The size of the
catch-up by day 7 depends on how fast Exophase rescans profiles, which could not be measured from outside; the priors
are judgement, not a fit, and no first-week history of a comparable launch exists to test them on. What the model does
guarantee is a median that moves with the recorded page and bands wide enough to cover a page that is half or twice as
fresh as assumed.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`input/` holds the case files (`<id>.in`); the forecast for each is written to `out/<id>.out`. Without the two
variables the program reads `/input` and writes `/output`, as the grader runs it.

---

<sub>Entered on [make.fun](https://make.fun/?ref=9ykrm1qx&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
