"""Unit tests for media transport state parsing logic."""
from __future__ import annotations

from desktop_harness import helpers


def test_media_state_pause_only_is_playing():
    nodes = [
        {"role": "AXButton", "label": "Pause"},
        {"role": "AXButton", "label": "Next Track"},
    ]
    res = helpers._media_state_from_nodes(nodes)
    assert res["state"] == "playing"
    assert res["pause"] is True
    assert res["play"] is False
    assert res["transport_play"] is False
    assert res["row_play"] is False


def test_media_state_play_only_is_paused():
    nodes = [
        {"role": "AXButton", "label": "Play", "_el": "mock_play_el"},
        {"role": "AXButton", "label": "Previous"},
    ]
    res = helpers._media_state_from_nodes(nodes)
    assert res["state"] == "paused"
    assert res["pause"] is False
    assert res["play"] is True
    assert res["transport_play"] is True
    assert res["_play_el"] == "mock_play_el"


def test_media_state_both_pause_and_play_trusts_pause():
    nodes = [
        {"role": "AXButton", "label": "Pause"},
        {"role": "AXButton", "label": "Play"},
    ]
    res = helpers._media_state_from_nodes(nodes)
    assert res["state"] == "playing"
    assert res["pause"] is True
    assert res["play"] is True


def test_media_state_row_play_is_unknown():
    nodes = [
        {"role": "AXButton", "label": "Play Song 1"},
        {"role": "AXButton", "label": "Play All"},  # Ignored from row_play
    ]
    res = helpers._media_state_from_nodes(nodes)
    assert res["state"] == "unknown"
    assert res["pause"] is False
    assert res["play"] is False
    assert res["row_play"] is True


def test_media_state_empty_nodes():
    res = helpers._media_state_from_nodes([])
    assert res["state"] == "unknown"
    assert res["pause"] is False
    assert res["play"] is False
    assert res["row_play"] is False
    assert res["labels"] == []
