"""Adversarial meaning-preservation tests (rules_v4) for Kannada, Hindi, Tamil, Telugu, their
Romanized forms and English-Indic code-mixing. Sentences are developer-written test inputs
(AI-drafted, not native-speaker reviewed). A critical change must be 'changed' (rejected); a
change the rule-based check cannot vouch for must be 'at_risk' (review required) — never
'preserved'."""
import pytest

from app.schemas import MeaningCheckRequest
from app.services import meaning


def check(o, c, lang):
    return meaning.check(MeaningCheckRequest(original=o, candidate=c, language=lang))


def lost(r, category):
    return any(f.category == category and f.state != "kept" for f in r.findings)


# (language, case, original, rewrite, expected category that changed)
CHANGED = [
    # ---- Kannada ----
    ("kn", "negation reversal", "ವರದಿಯನ್ನು ಕಳುಹಿಸಬೇಡಿ.", "ವರದಿಯನ್ನು ಕಳುಹಿಸಿ.", "negation"),
    ("kn", "must-not reversal", "ಇದನ್ನು ಮಾಡಬಾರದು.", "ಇದನ್ನು ಮಾಡಬೇಕು.", "negation"),
    ("kn", "condition removed", "ಮಳೆ ಬಂದರೆ ಮನೆಯಲ್ಲಿ ಇರಿ.", "ಮಳೆ ಬಂತು ಮನೆಯಲ್ಲಿ ಇರಿ.", "condition"),
    ("kn", "restriction removed", "ಕನ್ನಡದಲ್ಲಿ ಮಾತ್ರ ಉತ್ತರಿಸಿ.", "ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ.", "constraint"),
    ("kn", "number word changed", "ಐದು ಕೆಜಿ ಅಕ್ಕಿ ತನ್ನಿ.", "ಆರು ಕೆಜಿ ಅಕ್ಕಿ ತನ್ನಿ.", "number"),
    ("kn", "digit changed", "5 ಕೆಜಿ ಅಕ್ಕಿ ತನ್ನಿ.", "50 ಕೆಜಿ ಅಕ್ಕಿ ತನ್ನಿ.", "number"),
    ("kn", "unit changed", "5 ಕೆಜಿ ಅಕ್ಕಿ ತನ್ನಿ.", "5 ಗ್ರಾಂ ಅಕ್ಕಿ ತನ್ನಿ.", "number"),
    ("kn", "month changed", "ಮಾರ್ಚ್ 12 ರಂದು ಸಭೆ.", "ಏಪ್ರಿಲ್ 12 ರಂದು ಸಭೆ.", "datetime"),
    ("kn", "day changed", "ನಾಳೆ ಬನ್ನಿ.", "ಇಂದು ಬನ್ನಿ.", "datetime"),
    ("kn", "name changed", "ಶ್ರೀ ರಮೇಶ್ ಅವರಿಗೆ ಕರೆ ಮಾಡಿ.", "ಶ್ರೀ ಸುರೇಶ್ ಅವರಿಗೆ ಕರೆ ಮಾಡಿ.", "entity"),
    ("kn", "question word removed", "ಸಭೆ ಯಾವಾಗ ಇದೆ", "ಸಭೆ ಇದೆ", "question"),
    ("kn", "question mark removed", "ಸಭೆ ನಾಳೆ ಇದೆಯೇ?", "ಸಭೆ ನಾಳೆ ಇದೆಯೇ.", "question"),
    # ---- Hindi ----
    ("hi", "negation reversal", "कल रिपोर्ट मत भेजो।", "कल रिपोर्ट भेजो।", "negation"),
    ("hi", "forbidden removed", "यहाँ धूम्रपान मना है।", "यहाँ धूम्रपान है।", "negation"),
    ("hi", "condition removed", "अगर बारिश हो तो घर पर रहो।", "बारिश हो तो घर पर रहो।", "condition"),
    ("hi", "otherwise removed", "जल्दी आओ, वरना देर होगी।", "जल्दी आओ, देर होगी।", "condition"),
    ("hi", "restriction removed", "सिर्फ़ हिंदी में जवाब दो।", "हिंदी में जवाब दो।", "constraint"),
    ("hi", "at-least removed", "कम से कम तीन उदाहरण दो।", "तीन उदाहरण दो।", "constraint"),
    ("hi", "number word changed", "दो किलो चावल लाओ।", "तीन किलो चावल लाओ।", "number"),
    ("hi", "month changed", "मार्च में बैठक है।", "मई में बैठक है।", "datetime"),
    ("hi", "name changed", "श्री शर्मा को फ़ोन करो।", "श्री वर्मा को फ़ोन करो।", "entity"),
    ("hi", "question word removed", "बैठक कब है", "बैठक है", "question"),
    # ---- Tamil ----
    ("ta", "negation reversal", "அறிக்கையை அனுப்ப வேண்டாம்.", "அறிக்கையை அனுப்பவும்.", "negation"),
    ("ta", "must-not reversal", "இதைச் செய்யக்கூடாது.", "இதைச் செய்யலாம்.", "negation"),
    ("ta", "condition removed", "மழை வந்தால் வீட்டில் இருங்கள்.", "மழை வந்தது வீட்டில் இருங்கள்.", "condition"),
    ("ta", "restriction removed", "தமிழில் மட்டும் பதில் சொல்லுங்கள்.", "தமிழில் பதில் சொல்லுங்கள்.", "constraint"),
    ("ta", "number word changed", "இரண்டு கிலோ அரிசி வாங்குங்கள்.", "மூன்று கிலோ அரிசி வாங்குங்கள்.", "number"),
    ("ta", "day changed", "நாளை வாருங்கள்.", "இன்று வாருங்கள்.", "datetime"),
    ("ta", "name changed", "திரு ராமன் அவர்களை அழைக்கவும்.", "திரு கண்ணன் அவர்களை அழைக்கவும்.", "entity"),
    ("ta", "question word removed", "கூட்டம் எப்போது நடக்கும்", "கூட்டம் நடக்கும்", "question"),
    # ---- Telugu ----
    ("te", "negation reversal", "నివేదికను పంపవద్దు.", "నివేదికను పంపండి.", "negation"),
    ("te", "must-not reversal", "ఇది చేయకూడదు.", "ఇది చేయవచ్చు.", "negation"),
    ("te", "condition removed", "వర్షం వస్తే ఇంట్లో ఉండండి.", "వర్షం వచ్చింది ఇంట్లో ఉండండి.", "condition"),
    ("te", "restriction removed", "తెలుగులో మాత్రమే సమాధానం ఇవ్వండి.", "తెలుగులో సమాధానం ఇవ్వండి.", "constraint"),
    ("te", "number word changed", "రెండు కిలో బియ్యం తీసుకురండి.", "మూడు కిలో బియ్యం తీసుకురండి.", "number"),
    ("te", "month changed", "మార్చి 12న సమావేశం.", "ఏప్రిల్ 12న సమావేశం.", "datetime"),
    ("te", "name changed", "శ్రీ రావు గారికి ఫోన్ చేయండి.", "శ్రీ రెడ్డి గారికి ఫోన్ చేయండి.", "entity"),
    ("te", "question word removed", "సమావేశం ఎప్పుడు", "సమావేశం", "question"),
    # ---- Romanized (language given) ----
    ("hi", "romanized negation", "kal report mat bhejo", "kal report bhejo", "negation"),
    ("hi", "romanized condition", "agar baarish ho to ghar raho", "baarish ho to ghar raho", "condition"),
    ("hi", "romanized restriction", "sirf hindi mein jawab do", "hindi mein jawab do", "constraint"),
    ("hi", "romanized question", "meeting kab hai", "meeting hai", "question"),
    ("kn", "romanized negation", "report kalisabedi, naanu baruvudilla", "report kalisi, naanu baruvudu", "negation"),
    ("kn", "romanized restriction", "kannadadalli maatra uttarisi", "kannadadalli uttarisi", "constraint"),
    ("ta", "romanized restriction", "tamil-la mattum pathil sollunga", "tamil-la pathil sollunga", "constraint"),
    ("ta", "romanized must-not", "idhai seiyakoodathu", "idhai seiyalaam", "negation"),
    ("te", "romanized negation", "report pampakandi vaddu", "report pampandi", "negation"),
    ("te", "romanized question", "meeting eppudu", "meeting", "question"),
    # ---- code-mixed (language given) ----
    ("kn", "code-mixed condition", "Meeting cancel ಆದರೆ email ಕಳುಹಿಸಿ.", "Meeting cancel email ಕಳುಹಿಸಿ.", "condition"),
    ("hi", "code-mixed negation", "Kal ki meeting mein laptop mat lana.", "Kal ki meeting mein laptop lana.", "negation"),
    ("ta", "code-mixed number", "Report-ஐ 5 மணிக்கு send பண்ணுங்க.", "Report-ஐ 6 மணிக்கு send பண்ணுங்க.", "number"),
    ("te", "code-mixed restriction", "Python లో మాత్రమే code రాయండి.", "Python లో code రాయండి.", "constraint"),
]


@pytest.mark.parametrize("lang,case,original,rewrite,category", CHANGED, ids=[f"{c[0]}-{c[1]}" for c in CHANGED])
def test_critical_change_is_rejected(lang, case, original, rewrite, category):
    r = check(original, rewrite, lang)
    assert r.status == "changed", (case, [(f.category, f.state, f.example) for f in r.findings])
    assert lost(r, category), (case, [(f.category, f.state) for f in r.findings])


FORMALITY = [
    ("kn", "ನೀವು ನಾಳೆ ಬನ್ನಿ.", "ನೀನು ನಾಳೆ ಬಾ."),
    ("hi", "आप कल आइए।", "तुम कल आओ।"),
    ("ta", "நீங்கள் நாளை வாருங்கள்.", "நீ நாளை வா."),
    ("te", "మీరు రేపు రండి.", "నువ్వు రేపు రా."),
    ("hi", "कृपया रिपोर्ट भेजिए।", "रिपोर्ट भेजिए।"),
    ("kn", "ದಯವಿಟ್ಟು ವರದಿ ಕಳುಹಿಸಿ.", "ವರದಿ ಕಳುಹಿಸಿ."),
    ("hi", "aap kal aaiye", "tum kal aao"),
    ("en", "Please send the report.", "Send the report."),
]


@pytest.mark.parametrize("lang,original,rewrite", FORMALITY)
def test_formality_change_requires_review(lang, original, rewrite):
    r = check(original, rewrite, lang)
    assert r.status != "preserved"
    assert any(x.startswith(meaning.REGISTER_RISK_PREFIX) for x in r.risks) or r.status == "changed"


AMBIGUOUS = [   # words removed that no list covers: the check must not claim preservation
    ("kn", "ದಯವಿಟ್ಟು ಈ ವರದಿಯನ್ನು ಸರಿಯಾಗಿ ಓದಿ.", "ದಯವಿಟ್ಟು ಈ ವರದಿಯನ್ನು ಓದಿ."),
    ("hi", "इस रिपोर्ट को ध्यान से पढ़ो।", "इस रिपोर्ट को पढ़ो।"),
    ("ta", "இந்த அறிக்கையை கவனமாகப் படியுங்கள்.", "இந்த அறிக்கையைப் படியுங்கள்."),
    ("te", "ఈ నివేదికను జాగ్రత్తగా చదవండి.", "ఈ నివేదికను చదవండి."),
]


@pytest.mark.parametrize("lang,original,rewrite", AMBIGUOUS)
def test_ambiguous_shortening_is_never_preserved(lang, original, rewrite):
    r = check(original, rewrite, lang)
    assert r.status == "at_risk"
    assert any(x.startswith(meaning.MARKER_RISK_PREFIX) for x in r.risks)


@pytest.mark.parametrize("lang,a,b", [
    ("hi", "report nahi bhejna", "report nahin bhejna"),     # spelling variants, same negation
    ("hi", "report nhi bhejna", "report nahi bhejna"),
    ("ta", "varamudiyathu illai", "varamudiyathu illa"),
])
def test_romanized_spelling_variation_keeps_negation_but_asks_review(lang, a, b):
    r = check(a, b, lang)
    assert r.status != "changed" and not lost(r, "negation")
    assert r.status == "at_risk"


def test_code_mixed_without_language_requires_review():
    r = check("Meeting kal hai, ಮರೆಯಬೇಡಿ please.", "Meeting kal hai, ಮರೆಯಬೇಡಿ.", "auto")
    assert r.status != "preserved"
    r2 = check("Report bhejo ಈಗ", "Report ಈಗ", "auto")
    assert r2.status == "at_risk" and meaning.CODE_MIXED_RISK in r2.risks


def test_formatting_only_changes_stay_preserved_in_every_language():
    for lang, t in [("kn", "ನಾಳೆ  5 ಕೆಜಿ ಅಕ್ಕಿ ಮಾತ್ರ ತನ್ನಿ!!!"), ("hi", "कल  सिर्फ़ दो किलो चावल लाओ!!!"),
                    ("ta", "நாளை  இரண்டு கிலோ அரிசி மட்டும்!!!"), ("te", "రేపు  రెండు కిలో బియ్యం మాత్రమే!!!")]:
        r = check(t, t.replace("  ", " ").replace("!!!", "!"), lang)
        assert r.status == "preserved", (lang, r.risks)


def test_marker_lists_are_reported_as_pending():
    r = check("ಕನ್ನಡದಲ್ಲಿ ಮಾತ್ರ ಉತ್ತರಿಸಿ.", "ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ.", "kn")
    ids = {m.id: m.review_status for m in r.marker_lists}
    assert ids.get("kn-Knda-markers") == "unreviewed" and "kn-Latn-markers" in ids


def test_romanized_text_without_language_requires_review():
    # Latin-only Romanized Hindi with language 'auto': looks like English to the script detector,
    # so the check must ask for review when words change (rules_v4).
    r = check("kal report mat bhejo, kya samjhe? kal report mat bhejo.", "kal report mat bhejo, kya samjhe?", "auto")
    assert r.status == "at_risk" and any("Romanized" in x for x in r.risks)
    plain = check("Please read the full report carefully.", "Please read the report carefully.", "auto")
    assert plain.status == "preserved"                       # ordinary English is not affected


def test_romanized_kannada_negation_ending_detected():
    r = check("sign maadade kalisabedi", "sign maadade kalisi", "kn")
    assert r.status == "changed" and lost(r, "negation")


def test_invisible_characters_do_not_hide_words():
    # A zero-width space inside a word must not hide it from the lists: removing the invisible
    # character is formatting only and must stay 'preserved' (found by the FLORES re-evaluation).
    for lang, word in [("kn", "ಒಂದು"), ("kn", "ಎಲ್ಲಾ"), ("en", "AI")]:
        r = check(f"{word}\u200b ಮನೆ tool", f"{word} ಮನೆ tool", lang)
        assert r.status == "preserved", (lang, word, r.findings)
