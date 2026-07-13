"""Unit tests for the corpus seam."""

import json
import random

import pytest

from q20.game.corpus import BundledCorpus, Paragraph, load_corpus
from q20.shared.exceptions import CorpusError


def test_bundled_corpus_loads_and_samples(corpus):
    items = corpus.all()
    assert len(items) >= 3
    p = corpus.sample(random.Random(7))
    assert isinstance(p, Paragraph)
    assert p.opening_sentence and p.associative_word


def test_sample_is_deterministic_with_seed(corpus):
    a = corpus.sample(random.Random(1))
    b = corpus.sample(random.Random(1))
    assert a == b


def test_load_corpus_via_config(cfg):
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    c = load_corpus(cfg, root)
    assert len(c.all()) >= 1


def test_missing_file_raises(tmp_path):
    with pytest.raises(CorpusError):
        BundledCorpus.from_path(tmp_path / "nope.json")


def test_empty_corpus_raises():
    with pytest.raises(CorpusError):
        BundledCorpus([])


def test_bad_json_raises(tmp_path):
    bad = tmp_path / "c.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(CorpusError):
        BundledCorpus.from_path(bad)


def test_missing_field_raises():
    with pytest.raises(CorpusError):
        Paragraph.from_dict({"paragraph": "x"})


def test_unsupported_source_raises(cfg, tmp_path):
    cfg.setup["game"]["corpus"]["source"] = "wikipedia"
    with pytest.raises(CorpusError):
        load_corpus(cfg, tmp_path)


def test_list_shaped_json(tmp_path):
    items = [{"paragraph": "p", "opening_sentence": "s", "associative_word": "w"}]
    f = tmp_path / "list.json"
    f.write_text(json.dumps(items), encoding="utf-8")
    c = BundledCorpus.from_path(f)
    assert c.all()[0].associative_word == "w"
