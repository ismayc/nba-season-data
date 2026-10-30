"""Build the NBA 2025-26 season CSVs from pinned sportsdataverse hoopR files.

Run from this folder with the family venv:
    ../.venv/bin/python -I build.py

Downloads are cached in .cache/ (gitignored). Outputs go to data/2025-26/ plus
data/combine/, and data/manifest.json records every source URL, the pinned
commit, and each output's row count. Change a SHA below to rebuild from a newer
upstream commit, then rerun the checks (run_checks.sh).
"""

import json
import pathlib
import urllib.request

import polars as pl

HERE = pathlib.Path(__file__).resolve().parent
CACHE = HERE / ".cache"
OUT = HERE / "data"

# Upstream commits, pinned October 30, 2026
STATS_REPO = "sportsdataverse/hoopR-nba-stats-data"
STATS_SHA = "634d595f3742ea6d8d8960be14af75dc7bc1418d"
BOX_REPO = "sportsdataverse/hoopR-nba-data"
BOX_SHA = "e4a0559bf034cdcea9f896889bdfbeb4fab0bf61"

# In hoopR file names, 2026 is the 2025-26 season
SEASON = "2025-26"
FILE_YEAR = 2026
COMBINE_YEARS = range(2001, 2028)

SOURCES = {}


def fetch(repo, sha, path):
    """Download one upstream file once into .cache/ and return its local path."""
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
    local = CACHE / sha[:12] / path
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as r:
            local.write_bytes(r.read())
    SOURCES[path] = {"repo": repo, "commit": sha, "url": url}
    return local


def regular_season(path):
    return pl.read_parquet(path).filter(pl.col("season_type") == "Regular Season")


def build_per100(base, adv):
    """Totals per 100 of the player's own possessions (NBA.com `poss`)."""
    d = base.join(
        adv.select("player_id", "poss", "off_rating", "def_rating", "efg_pct"),
        on="player_id", how="left",
    )
    per100 = lambda c: (pl.col(c) / pl.col("poss") * 100).round(1)
    return d.select(
        "player_id",
        pl.col("player_name").alias("player"),
        pl.col("team_abbreviation").alias("team"),
        pl.col("gp").alias("g"),
        pl.col("min").round(0).cast(pl.Int64).alias("mp"),
        pl.col("poss").cast(pl.Int64),
        per100("pts").alias("pts"),
        per100("oreb").alias("orb"),
        per100("dreb").alias("drb"),
        per100("reb").alias("trb"),
        per100("ast").alias("ast"),
        per100("stl").alias("stl"),
        per100("blk").alias("blk"),
        per100("tov").alias("tov"),
        pl.col("off_rating").round(1).alias("o_rtg"),
        pl.col("def_rating").round(1).alias("d_rtg"),
        pl.col("efg_pct").round(3).alias("e_fg_percent"),
        pl.col("ft_pct").round(3).alias("ft_percent"),
    ).sort("mp", "player_id", descending=[True, False])


def build_shooting(base):
    """2-point and 3-point make rates and shares of field-goal attempts."""
    fg2a = pl.col("fga") - pl.col("fg3_a")
    fg2m = pl.col("fgm") - pl.col("fg3_m")
    ratio = lambda num, den: pl.when(den > 0).then(num / den).otherwise(None).round(3)
    return base.select(
        "player_id",
        pl.col("player_name").alias("player"),
        pl.col("team_abbreviation").alias("team"),
        pl.col("gp").alias("g"),
        pl.col("fga"),
        ratio(pl.col("fgm"), pl.col("fga")).alias("fg_percent"),
        ratio(fg2a, pl.col("fga")).alias("2pt_rate"),
        ratio(pl.col("fg3_a"), pl.col("fga")).alias("3pt_rate"),
        ratio(fg2m, fg2a).alias("2pt_percent"),
        ratio(pl.col("fg3_m"), pl.col("fg3_a")).alias("3pt_percent"),
    ).sort("fga", "player_id", descending=[True, False])


def build_box(path):
    """One row per player per game: regular season, play-in, and playoffs.

    ESPN codes season_type 2, 5, and 3. The All-Star games (teams such as WORLD,
    STARS, and STRIPES in 2026) are dropped: a team with fewer than 40 games is
    not one of the 30. The NBA Cup final stays in the regular season, as ESPN
    has it, although the NBA's official statistics leave it out.
    """
    d = pl.read_parquet(path)
    games = d.select("game_id", "team_abbreviation").unique().group_by("team_abbreviation").len()
    nba = games.filter(pl.col("len") >= 40)["team_abbreviation"].to_list()
    d = d.filter(
        pl.col("team_abbreviation").is_in(nba), pl.col("opponent_team_abbreviation").is_in(nba)
    ).with_columns(
        season_type=pl.col("season_type").replace_strict(
            {2: "Regular Season", 5: "Play-In", 3: "Playoffs"}, return_dtype=pl.String)
    )
    return d.select(
        "game_id", "game_date", "season_type",
        pl.col("athlete_id").alias("player_id"),
        pl.col("athlete_display_name").alias("player"),
        pl.col("team_abbreviation").alias("team"),
        pl.col("opponent_team_abbreviation").alias("opponent"),
        "home_away", "starter", "did_not_play",
        "minutes",
        pl.col("field_goals_made").alias("fgm"),
        pl.col("field_goals_attempted").alias("fga"),
        pl.col("three_point_field_goals_made").alias("fg3m"),
        pl.col("three_point_field_goals_attempted").alias("fg3a"),
        pl.col("free_throws_made").alias("ftm"),
        pl.col("free_throws_attempted").alias("fta"),
        pl.col("offensive_rebounds").alias("orb"),
        pl.col("defensive_rebounds").alias("drb"),
        pl.col("rebounds").alias("trb"),
        pl.col("assists").alias("ast"),
        pl.col("steals").alias("stl"),
        pl.col("blocks").alias("blk"),
        pl.col("turnovers").alias("tov"),
        pl.col("fouls").alias("pf"),
        pl.col("plus_minus").cast(pl.Int64, strict=False),
        pl.col("points").alias("pts"),
    ).sort("game_date", "game_id", "team", "player_id")


def build_combine():
    """Every NBA Draft Combine measurement, 2001 on: one row per attendance.

    A player who attended twice has two rows; players who skipped the combine
    (many international players) are absent. Lengths are in inches.
    """
    num = ["height_wo_shoes", "height_w_shoes", "wingspan", "standing_reach", "weight"]
    frames = []
    for y in COMBINE_YEARS:
        d = pl.read_parquet(fetch(
            STATS_REPO, STATS_SHA,
            f"nba_stats/draft_combine/parquet/draftcombineplayeranthro_{y}.parquet"))
        frames.append(d.select(
            pl.col("player_id").cast(pl.Int64),
            pl.col("player_name").alias("player"),
            pl.col("season").cast(pl.Int64).alias("combine_year"),
            "position",
            *[pl.col(c).cast(pl.Float64, strict=False) for c in num],
        ))
    return pl.concat(frames).sort("combine_year", "player", "player_id")


def main():
    stats = "nba_stats/leaguedash/parquet"
    base = regular_season(fetch(STATS_REPO, STATS_SHA, f"{stats}/player_stats_base_{FILE_YEAR}.parquet"))
    adv = regular_season(fetch(STATS_REPO, STATS_SHA, f"{stats}/player_stats_advanced_{FILE_YEAR}.parquet"))
    box = fetch(BOX_REPO, BOX_SHA, f"nba/player_box/parquet/player_box_{FILE_YEAR}.parquet")

    outputs = {
        f"{SEASON}/per100.csv": build_per100(base, adv),
        f"{SEASON}/shooting.csv": build_shooting(base),
        f"{SEASON}/box_scores.csv": build_box(box),
        "combine/anthro.csv": build_combine(),
    }
    rows = {}
    for name, frame in outputs.items():
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_csv(path)
        rows[name] = {"rows": frame.height, "columns": frame.width}
        print(f"{name}: {frame.height} rows, {frame.width} columns")

    manifest = {
        "season": SEASON,
        "outputs": rows,
        "sources": dict(sorted(SOURCES.items())),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")


if __name__ == "__main__":
    main()
