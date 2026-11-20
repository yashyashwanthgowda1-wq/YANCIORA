import unicodedata

from app.core.text import char_count, detect_script, guess_language, normalize, word_count

# Test fixtures written for unit tests only — not dataset samples.
KN = "ನಮಸ್ಕಾರ ಹೇಗಿದ್ದೀರಾ"
HI = "नमस्ते आप कैसे हैं"
TA = "வணக்கம் எப்படி இருக்கிறீர்கள்"
TE = "నమస్కారం ఎలా ఉన్నారు"


def test_normalize_nfc_and_whitespace():
    decomposed = unicodedata.normalize("NFD", "café")
    assert normalize(f"﻿  {decomposed} \t\n there ") == "café there"


def test_normalize_keeps_zwj_zwnj():
    s = "क्‍ष क्‌ष"
    assert normalize(s) == s


def test_word_count_ignores_punctuation_chunks():
    assert word_count("Hello , world — again!") == 3
    assert word_count(KN) == 2
    assert word_count(HI) == 4
    assert word_count("   ") == 0


def test_word_count_counts_digits():
    assert word_count("Order 42 now") == 3
    assert word_count("೨೦೨೬") == 1  # Kannada digits


def test_char_count_code_points():
    assert char_count("ab  c") == 4


def test_detect_script_native():
    assert detect_script(KN) == "Knda"
    assert detect_script(HI) == "Deva"
    assert detect_script(TA) == "Taml"
    assert detect_script(TE) == "Telu"
    assert detect_script("namaskara hegiddira") == "Latn"


def test_detect_script_mixed_and_empty():
    assert detect_script("Meeting ನಾಳೆ ಬೆಳಿಗ್ಗೆ at office") == "mixed"
    assert detect_script("123 !?") is None


def test_minor_second_script_not_mixed():
    # A single Latin letter in long Kannada text stays Kannada (below 10%).
    assert detect_script(KN * 3 + " A") == "Knda"


def test_guess_language():
    assert guess_language("Knda") == "kn"
    assert guess_language("Deva") == "hi"
    assert guess_language("Latn") is None
    assert guess_language("mixed") is None
    assert guess_language(None) is None
