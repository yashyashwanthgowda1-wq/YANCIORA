"""Feature 6 — script and transliteration variants (translit_v1).
Texts are unit-test fixtures for conversion mechanics, not dataset samples. Expected Romanized
spellings below are the engine's own output, checked against standard ISO 15919 where noted;
they are NOT native-speaker-approved (see docs/review/transliteration_spot_check.md)."""
import pytest
from pydantic import ValidationError

from app.schemas import OptimizeRequest, ScriptVariantsRequest
from app.services import optimizer as O
from app.services import transliteration as TL
from tests.conftest import FakeTokenizer

engine = pytest.importorskip("indic_transliteration", reason="indic-transliteration not installed")

BYTES = [FakeTokenizer()]
SCHEMES = ["iso", "itrans_dravidian", "hk_dravidian", "optitrans_dravidian", "baraha"]
SAMPLES = {
    "kn": "ಕನ್ನಡ ನಾನು ನಾಳೆ ಬರುವುದಿಲ್ಲ ಬೆಳಿಗ್ಗೆ ಹೊಸ",
    "hi": "मैं कल नहीं आऊंगा कृपया हिंदी",
    "ta": "நான் நாளை வரமாட்டேன் தமிழ் எழுது ஒன்று",
    "te": "నేను రేపు రాను తెలుగు ఎవరు ఒక",
}


def sv(text, language, **kw):
    kw.setdefault("tokenizers", ["fake_bytes"])
    return TL.script_variants(ScriptVariantsRequest(text=text, language=language, **kw), BYTES)


# ---------- round trips: 4 scripts x 5 schemes ----------
# Measured losses (engine behaviour, reported to the user — not hidden):
#   hi + itrans_dravidian: आऊंगा → 'AUMgA' → ॐगा ('AUM' is read back as the Om sign)
KNOWN_LOSSY = {("hi", "itrans_dravidian")}


@pytest.mark.parametrize("language", list(SAMPLES))
@pytest.mark.parametrize("scheme", SCHEMES)
def test_round_trip_matrix(language, scheme):
    v = sv(SAMPLES[language], language, target_schemes=[scheme]).variants[0]
    assert v.script == "Latn" and v.scheme == scheme and v.requires_review
    if (language, scheme) in KNOWN_LOSSY:
        assert not v.lossless_round_trip and v.lossy_reasons      # flagged, with the reason
    else:
        assert v.lossless_round_trip, v.lossy_reasons
    native = TL.LANG_SCRIPT[language][0]
    from app.core.text import script_of_char
    assert not any(script_of_char(c) == native for c in v.text)       # fully Romanized


def test_hindi_itrans_om_collision_is_reported():
    v = sv("आऊंगा", "hi", target_schemes=["itrans_dravidian"]).variants[0]
    assert v.text == "AUMgA" and not v.lossless_round_trip
    assert "ॐ" in v.lossy_reasons[0]


def test_hindi_baraha_chandrabindu_is_reported_lossy():
    v = sv("मैं कल नहीं आऊँगा", "hi", target_schemes=["baraha"]).variants[0]
    assert not v.lossless_round_trip and v.lossy_reasons


@pytest.mark.parametrize("text,language,expected", [
    ("ಕನ್ನಡ", "kn", "kannaḍa"),        # standard ISO 15919
    ("నేను", "te", "nēnu"),             # standard ISO 15919 (long ē)
    ("ಹೊಸ", "kn", "hosa"),             # short o kept distinct from ō
])
def test_iso_spot_checks(text, language, expected):
    assert sv(text, language).variants[0].text == expected


def test_ascii_schemes_are_ascii():
    for scheme in TL.ASCII_SCHEMES:
        for language, text in SAMPLES.items():
            out = sv(text, language, target_schemes=[scheme]).variants[0].text
            assert out.isascii(), (scheme, language, out)


# ---------- protection ----------
def test_protected_content_untouched():
    text = ('ನಾನು https://x.in/ಪುಟ ನೋಡಿ, mail a@b.in, run `ಕೋಡ್` and "ಕನ್ನಡ" ಸರಿ '
            "₹೫೦೦ ೧೨ Meeting today")
    v = sv(text, "kn", protected_terms=["ಸರಿ"]).variants[0]
    for kept in ("https://x.in/ಪುಟ", "a@b.in", "`ಕೋಡ್`", '"ಕನ್ನಡ"', "ಸರಿ", "₹೫೦೦", "೧೨",
                 "Meeting today"):
        assert kept in v.text, kept
    assert v.text.startswith("nānu ") and "nōḍi" in v.text
    assert v.protected_spans_skipped >= 6


def test_native_digits_never_converted():
    v = sv("ಸಂಖ್ಯೆ ೫೦೦ ಮತ್ತು 500", "kn").variants[0]
    assert "೫೦೦" in v.text and "500" in v.text and v.lossless_round_trip


def test_negations_are_converted_not_protected():
    v = sv("ನಾನು ಬರುವುದಿಲ್ಲ", "kn").variants[0]
    assert v.text == "nānu baruvudilla"


# ---------- ZWJ / ZWNJ ----------
def test_kannada_joiners_preserved():
    v = sv("ಕ್‍ಷ ಕ್‌ಷ", "kn").variants[0]
    assert v.joiners.source_count == 2 and v.joiners.preserved_in_round_trip
    assert v.lossless_round_trip


def test_devanagari_zwj_marker_reported():
    v = sv("क्‍ष क्‌ष", "hi").variants[0]
    assert v.joiners.source_count == 2 and v.joiners.preserved_in_round_trip
    assert "{}" in v.text and any("'{}'" in w for w in v.warnings)   # library ZWJ marker


# ---------- Tamil ----------
def test_tamil_forward_carries_convention_warning():
    for scheme in SCHEMES:
        v = sv(SAMPLES["ta"], "ta", target_schemes=[scheme]).variants[0]
        assert any("Sanskrit-style" in w for w in v.warnings)


def test_tamil_reverse_always_lossy():
    v = sv("nAn2 tamizh", "ta", direction="roman_to_native", source_scheme="itrans_dravidian").variants[0]
    assert not v.lossless_round_trip and "always lossy" in v.lossy_reasons[0]
    assert v.requires_review


# ---------- Romanized → native ----------
def test_reverse_with_named_scheme():
    r = sv("nAnu baruvudilla", "kn", direction="roman_to_native", source_scheme="itrans_dravidian")
    v = r.variants[0]
    assert r.status == "ok" and v.script == "Knda" and v.text == "ನಾನು ಬರುವುದಿಲ್ಲ"
    assert v.requires_review and v.lossless_round_trip
    assert any("English words" in w for w in v.warnings)


def test_reverse_converts_english_unless_protected():
    v = sv("nAnu Meeting", "kn", direction="roman_to_native", source_scheme="itrans_dravidian").variants[0]
    assert "Meeting" not in v.text and not v.lossless_round_trip
    v2 = sv("nAnu Meeting", "kn", direction="roman_to_native", source_scheme="itrans_dravidian",
            protected_terms=["Meeting"]).variants[0]
    assert v2.text == "ನಾನು Meeting"


def test_casual_romanization_unsupported():
    r = sv("naanu baruvudilla", "kn", direction="roman_to_native", source_scheme="casual")
    assert r.status == "unsupported" and r.variants == []
    assert "not supported" in r.warnings[0].lower()


def test_reverse_requires_source_scheme():
    with pytest.raises(ValidationError, match="source_scheme is required"):
        ScriptVariantsRequest(text="nAnu", language="kn", direction="roman_to_native")


# ---------- tokens, meaning, determinism ----------
def test_token_counts_use_registry_adapters():
    r = sv(SAMPLES["kn"], "kn", target_schemes=["iso", "baraha"])
    src = r.source.token_counts[0]
    assert src.tokenizer.name == "fake_bytes" and src.delta_vs_source == 0 and src.ratio_vs_source == 1.0
    for v in r.variants:
        tc = v.token_counts[0]
        assert tc.delta_vs_source == tc.tokens - src.tokens
        assert tc.ratio_vs_source == pytest.approx(tc.tokens / src.tokens)
        assert tc.status == "exact"
    assert any("not provider billing" in w for w in r.warnings)


def test_variant_meaning_check_present():
    v = sv("ನಾನು ಬರುವುದಿಲ್ಲ", "kn").variants[0]
    # Negation ಇಲ್ಲ → 'illa' matches the (unreviewed) Romanized list; Indic lists unreviewed → at_risk.
    assert v.meaning_check.status in ("at_risk", "changed")
    assert v.meaning_check.method == "rules_v1"


def test_deterministic():
    a = sv(SAMPLES["te"], "te", target_schemes=SCHEMES)
    b = sv(SAMPLES["te"], "te", target_schemes=SCHEMES)
    assert a.model_dump() == b.model_dump()


def test_library_identity_reported():
    r = sv("ಕನ್ನಡ", "kn")
    assert r.library.name == "indic_transliteration" and r.library.version == "2.3.82"
    assert r.method == "translit_v1" and r.limitations


@pytest.mark.parametrize("kwargs,msg", [
    ({"text": "hello", "language": "en"}, "kn, hi, ta and te only"),
    ({"text": "x", "language": "kn", "target_schemes": ["iast"]}, "Input should be"),
    ({"text": "x", "language": "kn", "target_schemes": ["iso", "iso"]}, "must not repeat"),
    ({"text": "   ", "language": "kn"}, "blank"),
    ({"text": "x" * 20_001, "language": "kn"}, "at most 20000"),
])
def test_request_validation(kwargs, msg):
    with pytest.raises(ValidationError, match=msg):
        ScriptVariantsRequest(**kwargs)


def test_unavailable_engine_raises(monkeypatch):
    TL._engine.cache_clear()
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name.startswith("indic_transliteration"):
            raise ImportError("missing")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    try:
        with pytest.raises(TL.TransliterationUnavailable):
            sv("ಕನ್ನಡ", "kn")
    finally:
        monkeypatch.undo()
        TL._engine.cache_clear()


# ---------- Feature 3 integration: never applied ----------
def test_optimizer_aggressive_offers_script_variants_only_as_suggestions():
    req = OptimizeRequest(text="ನಾನು   ನಾಳೆ ಬರುವುದಿಲ್ಲ", language="kn", mode="aggressive",
                          tokenizers=["fake_bytes"])
    r = O.optimize(req, BYTES)
    assert r.optimized == "ನಾನು ನಾಳೆ ಬರುವುದಿಲ್ಲ"                       # still Kannada
    scripts = [s for s in r.suggestions if s.kind == "script_variant"]
    assert scripts and all(s.requires_review for s in scripts)
    assert all(s.rule.startswith("script_variant:") for s in scripts)
    assert len({s.after for s in scripts}) == len(scripts)              # distinct variants only
    assert not any(a.rule.startswith("script_variant") for a in r.accepted)


def test_optimizer_safe_and_balanced_never_propose_script_variants():
    for mode in ("safe", "balanced"):
        r = O.optimize(OptimizeRequest(text="ನಾನು   ನಾಳೆ ಬರುವುದಿಲ್ಲ", language="kn", mode=mode,
                                       tokenizers=["fake_bytes"]), BYTES)
        assert not any(s.kind == "script_variant" for s in r.suggestions)


def test_optimizer_aggressive_english_explains_no_script_variants():
    r = O.optimize(OptimizeRequest(text="go   now", language="en", mode="aggressive",
                                   tokenizers=["fake_bytes"]), BYTES)
    assert any("need Kannada, Hindi, Tamil or Telugu" in w for w in r.warnings)
