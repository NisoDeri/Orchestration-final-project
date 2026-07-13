"""Shared test fixtures: a loaded config + the bundled corpus, rooted at the repo."""

from pathlib import Path

import pytest

from q20.game.corpus import load_corpus
from q20.shared.config import ConfigLoader

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg():
    return ConfigLoader(_ROOT / "config").load()


@pytest.fixture
def corpus(cfg):
    return load_corpus(cfg, _ROOT)
