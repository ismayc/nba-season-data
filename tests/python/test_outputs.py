"""Checks on the committed CSVs in data/ (no network needed)."""

import json
import pathlib
import re

import polars as pl
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SEASON = DATA / "2025-26"


@pytest.fixture(scope="module")
def per100():
    return pl.read_csv(SEASON / "per100.csv")


@pytest.fixture(scope="module")
def shooting():
    return pl.read_csv(SEASON / "shooting.csv")


@pytest.fixture(scope="module")
def box():
    return pl.read_csv(SEASON / "box_scores.csv", try_parse_dates=True)


@pytest.fixture(scope="module")
def combine():
    return pl.read_csv(DATA / "combine" / "anthro.csv")


def test_manifest_matches_outputs_and_build_pins():
    manifest = json.loads((DATA / "manifest.json").read_text())
    for name, info in manifest["outputs"].items():
        frame = pl.read_csv(DATA / name, infer_schema_length=0)
        assert (frame.height, frame.width) == (info["rows"], info["columns"]), name
    build = (ROOT / "build.py").read_text()
    pinned = set(re.findall(r'_SHA = "([0-9a-f]{40})"', build))
    assert {s["commit"] for s in manifest["sources"].values()} == pinned


def test_one_row_per_player(per100, shooting):
    assert per100["player_id"].is_unique().all()
    assert set(per100["player_id"]) == set(shooting["player_id"])
    assert per100.height == 582


def test_rebounds_add_up(per100):
    # Each per-100 value is rounded to 1 decimal, so the sum can be off by 0.1
    gap = (per100["orb"] + per100["drb"] - per100["trb"]).abs()
    assert gap.max() <= 0.15


def test_shot_shares_add_to_one(shooting):
    s = shooting.filter(pl.col("fga") > 0)
    assert ((s["2pt_rate"] + s["3pt_rate"] - 1).abs() <= 0.0015).all()


def test_top_five_points_per_100_match_basketball_reference(per100):
    # Basketball-Reference's 2025-26 per-100 page, 500+ minutes, read October 30, 2026
    top = per100.filter(pl.col("mp") >= 500).sort("pts", descending=True).head(5)
    assert top["player"].to_list() == [
        "Giannis Antetokounmpo", "Luka Dončić", "Shai Gilgeous-Alexander",
        "Kawhi Leonard", "Jaylen Brown",
    ]


def test_box_scores_season_shape(box):
    games = box.select("game_id", "season_type").unique()
    counts = dict(games.group_by("season_type").len().rows())
    assert counts == {"Regular Season": 1231, "Play-In": 6, "Playoffs": 85}
    team_games = (
        box.filter(pl.col("season_type") == "Regular Season")
        .select("game_id", "team").unique().group_by("team").len()
    )
    assert team_games.height == 30
    # 82 each, plus the NBA Cup final for its two teams
    assert sorted(team_games["len"].to_list()) == [82] * 28 + [83] * 2
    assert box["game_date"].min().isoformat() == "2025-10-21"
    assert box["game_date"].max().isoformat() == "2026-06-13"


def test_box_points_add_up(box):
    played = box.filter(~pl.col("did_not_play"))
    pts = 2 * (played["fgm"] - played["fg3m"]) + 3 * played["fg3m"] + played["ftm"]
    assert (pts == played["pts"]).all()


def test_combine_lengths(combine):
    assert combine["combine_year"].min() == 2001
    w = combine.filter(pl.col("wingspan").is_not_null())
    # Tacko Fall (2020) has the longest: 98.25 inches
    assert w["wingspan"].is_between(66, 100).all()
    assert w["player_id"].n_unique() == 1753


def test_combine_coverage_of_current_players(per100, combine):
    measured = set(combine.filter(pl.col("wingspan").is_not_null())["player_id"])
    assert len(set(per100["player_id"]) & measured) == 363
