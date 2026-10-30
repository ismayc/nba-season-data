# NBA season data

Player tables for the NBA 2025-26 season, plus every NBA Draft Combine
measurement since 2001, as plain CSV files. They are built by one script from
pinned files in the sportsdataverse hoopR data repos, and checked on every
change. Part of the [basketball-data-science](https://github.com/ismayc/basketball-data-science)
family. The course *Thinking Critically with Data in Python* reads these files
in the browser.

## Files

| File | Rows | One row per | Columns |
|---|---|---|---|
| `data/2025-26/per100.csv` | 582 | player, regular season | `player_id`, `player`, `team`, games `g`, minutes `mp`, possessions `poss`, then per 100 possessions: `pts`, `orb`, `drb`, `trb`, `ast`, `stl`, `blk`, `tov`; offensive and defensive rating `o_rtg`, `d_rtg`; `e_fg_percent`, `ft_percent` |
| `data/2025-26/shooting.csv` | 582 | player, regular season | `player_id`, `player`, `team`, `g`, `fga`, `fg_percent`, `2pt_rate` and `3pt_rate` (shares of field-goal attempts), `2pt_percent`, `3pt_percent` |
| `data/2025-26/box_scores.csv` | 34,810 | player per game | `game_id`, `game_date`, `season_type` (Regular Season, Play-In, Playoffs), `player_id`, `player`, `team`, `opponent`, `home_away`, `starter`, `did_not_play`, `minutes`, made and attempted shots, rebounds, `ast`, `stl`, `blk`, `tov`, `pf`, `plus_minus`, `pts` |
| `data/combine/anthro.csv` | 1,873 | player per combine attended, 2001 to 2027 | `player_id`, `player`, `combine_year`, `position`, `height_wo_shoes`, `height_w_shoes`, `wingspan`, `standing_reach` (inches), `weight` (pounds) |

`data/manifest.json` lists every source file's URL and pinned commit, and the
row and column count of each output.

To read a file without cloning, use its raw URL, for example
`https://raw.githubusercontent.com/ismayc/nba-season-data/main/data/2025-26/per100.csv`.
GitHub serves raw files with `Access-Control-Allow-Origin: *`, so a page in a
browser (Pyodide, JupyterLite) can read them too.

## What to know before using them

- **Per 100 possessions** is each total divided by the player's own possessions
  (NBA.com's `poss`), times 100. It runs about 1 to 4 percent below
  Basketball-Reference's per-100 page, which estimates possessions another way.
  The top five in points per 100 (500 or more minutes) match Basketball-Reference's
  top five, in order; a check holds that.
- **Traded players** have one row for the season, with the team they ended it on.
- **Box scores** come from ESPN, so their `player_id` is ESPN's, not NBA.com's,
  and names are spelled as ESPN spells them. The All-Star games are dropped. The
  NBA Cup final stays in the regular season, as ESPN has it, so its two teams
  show 83 regular-season games; the NBA's official statistics leave that game out.
- **Combine measurements** exist only for players who attended a combine. Of the
  582 players in 2025-26, 363 have a wingspan; most of the rest came from abroad
  or skipped the combine. A player who attended twice has two rows.
- **Not included:** shot distance and dunk rate, which the source files lack.

## Sources and terms

- Season tables and combine measurements: NBA.com statistics, through
  [hoopR-nba-stats-data](https://github.com/sportsdataverse/hoopR-nba-stats-data).
- Box scores: ESPN, through [hoopR-nba-data](https://github.com/sportsdataverse/hoopR-nba-data).

Both hoopR repos label their contents CC BY 4.0 (in `LICENSE.md`). The files
here are derived from them: filtered to the regular season or by game, renamed,
and with per-100 rates and shooting shares computed, as `build.py` shows.

The underlying statistics belong to their sources. NBA.com's
[terms of use](https://www.nba.com/termsofuse) say that NBA statistics may only
be used for legitimate news reporting or private, non-commercial purposes, with
prominent attribution to NBA.com. This repo does not grant any rights that the
NBA, ESPN, or the hoopR authors do not. Check those terms before you use the
data.

## Rebuild and check

```bash
../.venv/bin/python -I build.py   # downloads into .cache/, writes data/
./run_checks.sh                   # checks the committed CSVs
```

To move to a newer upstream commit, change `STATS_SHA` or `BOX_SHA` in
`build.py`, rebuild, and update any count the checks hold.
