"""Isolated fixture data for persistence/API tests. Texts are unit-test fixtures written
for these tests, not dataset samples, and the register entry is a fake test dataset."""

LICENSE = "TEST-LICENCE"


def register(name="TESTSET", version="1", **over):
    e = {"name": name, "version": version, "license": LICENSE, "license_url": None,
         "source_url": "http://example.test/testset", "citation": "unit test fixture",
         "accessed_at": "2026-11-20", "approved_for": ["evaluation"],
         "languages": ["en", "kn", "hi", "ta", "te"]}
    e.update(over)
    return [e]


def row(sid, lang, script, text, group, split="test", vt="translation", **over):
    r = {"sample_id": sid, "language_code": lang, "script": script, "text": text,
         "aligned_group_id": group, "variant_type": vt, "source_name": "unit-test",
         "split": split, "domain": "general"}
    r.update(over)
    return r


def rows():
    return [
        row("g1-en", "en", "Latn", "Good morning friend", "g1", vt="original"),
        row("g1-kn", "kn", "Knda", "ಶುಭೋದಯ ಗೆಳೆಯ", "g1"),
        row("g1-hi", "hi", "Deva", "सुप्रभात दोस्त", "g1"),
        row("g2-en", "en", "Latn", "Where is the bus stop", "g2", vt="original"),
        row("g2-hi", "hi", "Deva", "बस स्टॉप कहाँ है", "g2"),
        row("g3-en", "en", "Latn", "Please call me tomorrow", "g3", split="train", vt="original"),
        row("g3-ta", "ta", "Taml", "நாளை என்னை அழைக்கவும்", "g3", split="train"),
    ]


def processed(rows_, name="TESTSET", version="1"):
    """What import_pilot.py writes to samples.jsonl (validated + dataset fields)."""
    from app.services.dataset_import import validate

    out, rep = validate(rows_, name, version)
    assert rep.ok, rep.errors
    return out
