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

Two days after launch the page is early in a long game, and players have a weekend and three more days ahead:

- 39.6 hours after launch the page showed 44,161 tracked players: 12.0 % with Chapter 1, 1.7 % with Chapter 2.
  50.2 hours after launch it showed 54,144: 18.0 % and 3.6 %, with Chapter 3 at 0.07 % (38 players) and everything
  after it at 0.03 % (about 16 early-copy players). A second tracker with 91,204 owners read 17.6 %, 3.2 % and 0.06 %
  at the same hour, so the page is close to real play, not far behind it.
- Chapter 2 climbs as steeply, in logit against log time, as Chapter 1 would have at half the hours, and "Trust"
  follows Chapter 1 at about two thirds of the clock. Reading every story trophy off Chapter 1's curve at
  168 h / c, and carrying Chapter 1 itself on along its probit line with some allowance for players who stop, puts
  Chapter 1 near 55 % at the target, Chapter 2 near 30 %, Chapter 3 near 5 % and the final mission near 1 %.
- Trophies earned inside story missions keep their ratio to the chapter they sit in; cumulative ones (100 vehicles,
  $100,000 spent) rise with hours played; early optional ones (fishing, an arcade game) rise slowly.

So nearly every rate should rise over the four and a half days after the deadline, the late story by several logits,
while pure grind trophies (100 %, 250 stunts, 100 photo spots) stay at the 0.01 % clamp.

## The model

For each trophy three views of its logit rate at the target are blended:

| view | what it says | weight (trend usable / not) |
| --- | --- | --- |
| P, prior | a typed median for the displayed rate a week after launch, reasoned from what the trophy asks for | 0.10 / 0.50 |
| S, shifted | the last recorded rate plus the share of the prior's drift that is still ahead of the last read | 0.15 / 0.50 |
| A, trend | the trophy's own last-day slope of probit against ln(1 + hours since launch), damped to 90 % and clipped | 0.75 / 0 |

The trend's weight and damping come from a backtest on archived first weeks of four big story launches
(Cyberpunk 2077, Elden Ring, Hogwarts Legacy, Red Dead Redemption 2): extending two early reads of every achievement
to a later read, the logit pinball loss was 0.31-0.37 for holding rates flat, 0.15 for half the slope and 0.07-0.08
for 85-100 % of it.

- Why probit: if the hours a player needs to reach a trophy are lognormal across players who keep arriving at a
  steady pace, the rate is a normal CDF of log time and its probit is a straight line. The reads agree: between 39.6 h
  and 50.2 h the probit slopes of Chapter 1, Chapter 2, Trust, 100 vehicles, bowling and the UFO scene were all
  1.1-1.35, while their logit slopes ran from 2.0 to 3.3 depending on how rare each still was.
- The trend is measured over a whole day (so the hour of the day cancels) between the moments the page actually
  changed (Exophase refreshes its counts in steps), and is used only when at least 40 tracked players hold the trophy
  now and 12 did at the earlier read; below that a 2-decimal page is rounding noise.
- S makes the forecast follow the page: if the recorded rates run ahead of the prior's path the median rises, and if
  the page stalls the median falls.
- The spread is a normal on the logit scale: the trophy's prior uncertainty (0.45-0.6 for early optional trophies, 0.55-0.75
  for the first chapters, 1.15-1.3 for late story and floor trophies) combined with 45 % of the gap between the most
  and least optimistic view.
- Story chapters are kept in order (a later chapter is never forecast above an earlier one), no median exceeds 93 %
  except the opening mission's, which has read 100.00 % in every read and is forecast to stay there.
- Quantiles are clamped to 0.01..99.99 like the scorer's logit, so floor trophies get quantiles on the floor.
- On launch night (fewer than 2,000 tracked players, the practice cases) the page is the pre-refresh one; the rules
  describe the first refresh as a jump from 638 to 3,868 tracked players that lowered every rate. A rate on that page
  is a whole number of early holders over 638, and players who started at launch cannot hold a late trophy 90 minutes
  later, so the forecast there is the same holders over 3,868, with the top quantile one holder higher. This branch
  only serves the practice cases; the final case never enters it.
- A trophy the table does not know (if the list changes) gets a modest catch-up and a wide spread; any failure inside
  a case falls back to a wide band around its last rates, so the output is always valid.

The priors, the snapshot they start from and the reasoning behind each group are in the `PRIOR` table in `main.py`.

## How sure this is

Moderately for the trophies that already move, and not very for the late story, and the spreads say so: the 5-95 %
band for Chapter 1 runs from roughly 27 % to 68 %, the one for the final mission from 0.1 % to 8 %. The priors are
judgement resting on two reads of the page 10.6 hours apart and one curve-shape assumption, not a fit, and no
first-week history of a comparable launch exists to test them on. What the model does guarantee is a median that
moves with the recorded page (the last day of reads enters through the trend and the shifted view) and bands wide
enough to cover a weekend that is half or twice as busy as assumed.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`input/` holds the case files (`<id>.in`); the forecast for each is written to `out/<id>.out`. Without the two
variables the program reads `/input` and writes `/output`, as the grader runs it.

---

<sub>Entered on [make.fun](https://make.fun/?ref=9ykrm1qx&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
