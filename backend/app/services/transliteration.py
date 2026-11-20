"""Script and transliteration variants (Feature 6, translit_v1).

Native script → Romanized (ISO 15919 default; ASCII alternatives), and Romanized → native
only from an explicitly named scheme. Uses the `indic_transliteration` (sanscript) engine,
imported lazily: if it is not installed, TransliterationUnavailable is raised (API → 503).

Never applies anything: every variant has requires_review = true. Token counts come from the
existing tokenizer registry and are tokenizer counts, not provider billing; fewer tokens does
not mean a model understands the text equally well.
"""
from __future__ import annotations

from functools import lru_cache

from app.core import details as D
from app.core import text as T
from app.core.metrics import fertility, relative_ratio
from app.schemas import (
    JoinerReport, MeaningCheckRequest, ScriptSource, ScriptVariant, ScriptVariantsRequest,
    ScriptVariantsResponse, TranslitLibrary, VariantTokenCount,
)
from app.services.counting import tokenizer_ref
from app.services.meaning import check as meaning_check
from app.tokenizers import TokenizerAdapter, get_tokenizer

METHOD_ID = "translit_v1"
DEFAULT_SCHEME = "iso"
ASCII_SCHEMES = ("itrans_dravidian", "hk_dravidian", "optitrans_dravidian", "baraha")
# language → (ISO 15924 script, sanscript scheme name)
LANG_SCRIPT = {"kn": ("Knda", "kannada"), "hi": ("Deva", "devanagari"),
               "ta": ("Taml", "tamil"), "te": ("Telu", "telugu")}
JOINERS = ("‍", "‌")
# Detail categories never transliterated. Negations are NOT protected: they are words of the
# text and must be converted with it (the meaning check still compares them).
PROTECTED_CATEGORIES = {"code", "url", "email", "quoted", "protected_term", "number", "money",
                        "datetime"}

BILLING_WARNING = ("Token counts are tokenizer counts, not provider billing. Fewer tokens does "
                   "not mean a model understands the text equally well.")
SCHEME_WARNING = ("Scheme Romanization differs from everyday Romanized typing (e.g. Hindi कमल "
                  "→ 'kamala', typed as 'kamal'); counts describe the scheme text only.")
TAMIL_FORWARD_WARNING = ("Tamil: this library maps Tamil consonants to Sanskrit-style values "
                         "(e.g. த → 'dh', ட → 'ḍh'), so the output is not standard Tamil "
                         "romanization. Native-speaker review pending.")
TAMIL_REVERSE_REASON = ("Tamil script has no separate letters for aspirated or voiced consonants "
                        "(ka/kha/ga/gha → க): Romanized → Tamil is always lossy.")
DEVANAGARI_ZWJ_WARNING = ("The library writes a Devanagari ZWJ as the marker '{}' in Romanized "
                          "text.")
REVERSE_WARNING = ("Romanized → native converts every unprotected Latin word, including English "
                   "words in code-mixed text. Add English words to protected_terms. Always review.")
CASUAL_REASON = ("Everyday Romanized typing follows no standard scheme, so converting it would "
                 "mean guessing. Not supported: name the scheme the text was written in.")
LIMITATIONS = [
    "Deterministic scheme transliteration (translit_v1) with indic_transliteration; it changes "
    "the script, not the language or wording.",
    "Round-trip checks show whether the conversion is reversible for this text; they do not show "
    "that the output is how native speakers would write it. Native-speaker spot checks pending.",
    "Romanized → native requires a named scheme; everyday Romanized typing is not supported.",
    "Script changes are never applied automatically.",
]


class TransliterationUnavailable(RuntimeError):
    pass


@lru_cache
def _engine():
    try:
        from indic_transliteration import sanscript
    except ImportError as exc:
        raise TransliterationUnavailable(
            "indic-transliteration is not installed (see backend/requirements-translit.txt)") from exc
    return sanscript


@lru_cache
def library_version() -> str:
    try:
        from importlib.metadata import version

        return version("indic_transliteration")
    except Exception:
        return "unknown"


def _transliterate(text: str, src: str, dst: str) -> str:
    return _engine().transliterate(text, src, dst)


# ---------- span selection ----------
def _protected_spans(src: str, req: ScriptVariantsRequest) -> list[tuple[int, int]]:
    lexes = D.active_lexicons(req.language, src)
    found = D.extract_details(src, protected_terms=req.protected_terms, lexicons=lexes)
    return [(d.start, d.end) for d in found if d.category in PROTECTED_CATEGORIES]


def _in_any(i: int, spans: list[tuple[int, int]]) -> bool:
    return any(s <= i < e for s, e in spans)


def native_runs(src: str, script: str, protected: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Maximal runs of the target script's letters/marks (plus joiners inside a run), outside
    protected spans. Digits are never part of a run, so they are kept as written."""
    runs, start = [], None
    for i, ch in enumerate(src):
        ok = (not _in_any(i, protected) and not ch.isdigit()
              and (T.script_of_char(ch) == script or (start is not None and ch in JOINERS)))
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(src)))
    # A run must not end with a dangling joiner.
    return [(s, e - (1 if src[e - 1] in JOINERS else 0)) for s, e in runs]


def roman_segments(src: str, protected: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Unprotected segments that contain Latin letters (for roman_to_native)."""
    segs, start = [], 0
    bounds = sorted(protected) + [(len(src), len(src))]
    for s, e in bounds:
        if s > start:
            segs.append((start, s))
        start = max(start, e)
    return [(s, e) for s, e in segs if any(T.script_of_char(c) == "Latn" for c in src[s:e])]


def _rebuild(src: str, spans: list[tuple[int, int]], replacements: list[str]) -> str:
    out, pos = [], 0
    for (s, e), r in zip(spans, replacements):
        out.append(src[pos:s])
        out.append(r)
        pos = e
    out.append(src[pos:])
    return "".join(out)


def _joiners(text: str) -> int:
    return sum(text.count(j) for j in JOINERS)


# ---------- token counts ----------
def _counts(text: str, adapters: list[TokenizerAdapter],
            base: dict[str, int] | None = None) -> tuple[list[VariantTokenCount], dict[str, int]]:
    words = T.word_count(text)
    raw = {a.info.name: a.count(text) for a in adapters}
    base = base or raw
    return [VariantTokenCount(
        tokenizer=tokenizer_ref(a), status=a.count_status, tokens=raw[a.info.name],
        tokens_per_word=fertility(raw[a.info.name], words),
        delta_vs_source=raw[a.info.name] - base[a.info.name],
        ratio_vs_source=relative_ratio(raw[a.info.name], base[a.info.name]),
    ) for a in adapters], raw


def _meaning(src: str, variant: str, req: ScriptVariantsRequest):
    return meaning_check(MeaningCheckRequest(original=src, candidate=variant, language=req.language,
                                             protected_terms=req.protected_terms))


# ---------- variants ----------
def _forward(src: str, req: ScriptVariantsRequest, scheme: str, adapters, base) -> ScriptVariant:
    script, engine_name = LANG_SCRIPT[req.language]
    protected = _protected_spans(src, req)
    runs = native_runs(src, script, protected)
    originals = [src[s:e] for s, e in runs]
    converted = [_transliterate(o, engine_name, scheme) for o in originals]
    back = [_transliterate(c, scheme, engine_name) for c in converted]
    text = _rebuild(src, runs, converted)

    reasons = [f"'{o}' → '{c}' → '{b}' does not round-trip"
               for o, c, b in zip(originals, converted, back) if b != o][:5]
    src_j = sum(_joiners(o) for o in originals)
    warnings = [SCHEME_WARNING]
    if req.language == "ta":
        warnings.append(TAMIL_FORWARD_WARNING)
    if script == "Deva" and "{}" in text and "{}" not in src:
        warnings.append(DEVANAGARI_ZWJ_WARNING)
    if not runs:
        warnings.append(f"No {script} text outside protected details was found; nothing converted.")
    counts, _ = _counts(text, adapters, base)
    return ScriptVariant(
        script="Latn", scheme=scheme, text=text,
        lossless_round_trip=not reasons, lossy_reasons=reasons,
        converted_spans=len(runs), protected_spans_skipped=len(protected),
        joiners=JoinerReport(source_count=src_j, output_count=_joiners(text),
                             preserved_in_round_trip=sum(_joiners(b) for b in back) == src_j),
        token_counts=counts, meaning_check=_meaning(src, text, req), warnings=warnings)


def _reverse(src: str, req: ScriptVariantsRequest, adapters, base) -> ScriptVariant:
    script, engine_name = LANG_SCRIPT[req.language]
    scheme = req.source_scheme
    protected = _protected_spans(src, req)
    segs = roman_segments(src, protected)
    originals = [src[s:e] for s, e in segs]
    converted = [_transliterate(o, scheme, engine_name) for o in originals]
    back = [_transliterate(c, engine_name, scheme) for c in converted]
    text = _rebuild(src, segs, converted)

    reasons = [f"'{o}' → '{c}' → '{b}' does not round-trip"
               for o, c, b in zip(originals, converted, back) if b != o][:5]
    if req.language == "ta":
        reasons.insert(0, TAMIL_REVERSE_REASON)
    src_j = sum(_joiners(o) for o in originals)
    counts, _ = _counts(text, adapters, base)
    return ScriptVariant(
        script=script, scheme=None, text=text,
        lossless_round_trip=not reasons, lossy_reasons=reasons,
        converted_spans=len(segs), protected_spans_skipped=len(protected),
        joiners=JoinerReport(source_count=src_j, output_count=_joiners(text),
                             preserved_in_round_trip=sum(_joiners(b) for b in back) == src_j),
        token_counts=counts, meaning_check=_meaning(src, text, req),
        warnings=[REVERSE_WARNING])


def script_variants(req: ScriptVariantsRequest,
                    adapters: list[TokenizerAdapter] | None = None) -> ScriptVariantsResponse:
    adapters = adapters or [get_tokenizer(n) for n in req.tokenizers]
    src = D.nfc(req.text)
    script, _ = LANG_SCRIPT[req.language]
    source_counts, base = _counts(src, adapters)
    reverse = req.direction == "roman_to_native"
    source = ScriptSource(script=("Latn" if reverse else script),
                          scheme=(req.source_scheme if reverse and req.source_scheme != "casual"
                                  else None),
                          text=src, token_counts=source_counts)
    common = dict(method=METHOD_ID, language=req.language, direction=req.direction, source=source,
                  library=TranslitLibrary(name="indic_transliteration", version=library_version()),
                  limitations=LIMITATIONS)

    if reverse and req.source_scheme == "casual":
        return ScriptVariantsResponse(status="unsupported", variants=[],
                                      warnings=[CASUAL_REASON, BILLING_WARNING], **common)
    _engine()  # raise TransliterationUnavailable before doing any work
    if reverse:
        variants = [_reverse(src, req, adapters, base)]
    else:
        variants = [_forward(src, req, s, adapters, base) for s in req.target_schemes]
    warnings = [BILLING_WARNING]
    detected = T.detect_script(T.normalize(src))
    if not reverse and detected not in (script, "mixed"):
        warnings.append(f"The text is mostly {detected or 'not letters'}, not {script}; only "
                        f"{script} spans are converted.")
    return ScriptVariantsResponse(status="ok", variants=variants, warnings=warnings, **common)
