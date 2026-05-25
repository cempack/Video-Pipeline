"""Tests for techniques from faceless AI channel workflows."""

from video_factory.models.schemas import LibraryAsset, LibraryIndex
from video_factory.utils.asset_library import find_library_match
from video_factory.utils.title import hook_word_budget, title_fits_homepage


def test_title_homepage_fit():
    ok, _ = title_fits_homepage("Short title", 60)
    assert ok
    ok, _ = title_fits_homepage("x" * 80, 60)
    assert not ok


def test_hook_word_budget():
    assert hook_word_budget(45, hook_sec=3.0) >= 5


def test_library_match():
    index = LibraryIndex(
        assets=[
            LibraryAsset(
                asset_id="lib_0001",
                description="character using a megaphone on stage",
                path="assets/lib_0001.png",
                style="editorial illustration",
            )
        ]
    )
    match = find_library_match(
        index,
        "A person speaks into a megaphone on stage",
        "editorial illustration",
    )
    assert match is not None
    assert match.asset_id == "lib_0001"
