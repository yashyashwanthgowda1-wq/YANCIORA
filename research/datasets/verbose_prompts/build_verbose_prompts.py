"""Build the verbose-prompt test set v1 (synthetic, AI-drafted, pending native-speaker review).

100 prompts: 20 per language (English, Kannada, Hindi, Tamil, Telugu). Each Indic language has 16
native-script prompts and 4 Romanized / code-mixed prompts. Prompts are composed deterministically
from small hand-written sentence banks below, so the set is reproducible and its redundancy is
known by construction:
  - "exact"  : one instruction is repeated word for word (removable without losing content);
  - "near"   : one instruction is repeated in different words (NOT removable by exact-repeat rules);
  - "none"   : no repeat; only wordy phrasing and formatting noise.
Every prompt holds critical details (numbers, dates, negations, constraints) so the meaning
check is exercised. English prompts also contain wordy phrases.

This is test data for the optimizer, not real user prompts. Results on it must be reported as
synthetic. Usage: python research/datasets/verbose_prompts/build_verbose_prompts.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).with_name("verbose_prompts_v1.jsonl")
SCRIPT = {"en": "Latn", "kn": "Knda", "hi": "Deva", "ta": "Taml", "te": "Telu"}
CATS = ["education", "programming", "business", "agriculture", "travel", "scheduling",
        "summarization", "assistant"]

BANK = {
    "en": {
        "open": ["Hello! I would like you to help me with a task that is quite important for my work.",
                 "Hi there. I hope you are doing well. It is important to note that I need your help with something.",
                 "Good morning. As you may already know, I am working on a project and I need some assistance."],
        "task": ["Please provide a summary of the attached quarterly sales report in a clear and concise manner.",
                 "In order to help the new interns, provide an explanation of how Git branching works.",
                 "Conduct an analysis of the customer feedback that we have collected on a monthly basis.",
                 "Provide a description of the best irrigation schedule for tomato crops in the near future.",
                 "Make a comparison between train travel and bus travel from Bengaluru to Mysuru.",
                 "Give a summary of the meeting notes due to the fact that I missed the meeting.",
                 "Write a Python function that is able to remove duplicate rows from a CSV file.",
                 "Provide a list of tasks for the product launch, taking into consideration the end result we want."],
        "cons": ["The answer must have exactly 5 bullet points.",
                 "Keep the response under 150 words.",
                 "The deadline is 15 December 2026.",
                 "Use at most 3 short paragraphs.",
                 "Include the total cost of Rs 25,000 in the answer."],
        "neg": ["Do not include any customer names.",
                "Do not use technical jargon.",
                "Never share the internal pricing.",
                "Do not exceed one page."],
        "fmt": ["Format the output as a table with two columns.",
                "Write the final answer in a professional manner.",
                "Use a numbered list for the steps."],
        "near": [("Do not include any customer names.", "Remember that customer names must not appear anywhere."),
                 ("Keep the response under 150 words.", "Again, the whole response should stay below 150 words.")],
    },
    "kn": {
        "open": ["ನಮಸ್ಕಾರ! ನನಗೆ ಒಂದು ಮುಖ್ಯವಾದ ಕೆಲಸದಲ್ಲಿ ನಿಮ್ಮ ಸಹಾಯ ಬೇಕು.",
                 "ದಯವಿಟ್ಟು ಈ ಕೆಳಗಿನ ಕೆಲಸವನ್ನು ಗಮನವಿಟ್ಟು ಮಾಡಿ.",
                 "ನಾನು ಒಂದು ಯೋಜನೆಯ ಮೇಲೆ ಕೆಲಸ ಮಾಡುತ್ತಿದ್ದೇನೆ, ಅದಕ್ಕಾಗಿ ನಿಮ್ಮ ಸಹಾಯ ಬೇಕು."],
        "task": ["ಈ ತ್ರೈಮಾಸಿಕ ಮಾರಾಟ ವರದಿಯ ಸಾರಾಂಶವನ್ನು ಸರಳವಾಗಿ ಬರೆಯಿರಿ.",
                 "ಹೊಸ ವಿದ್ಯಾರ್ಥಿಗಳಿಗೆ ದ್ಯುತಿಸಂಶ್ಲೇಷಣೆಯನ್ನು ಸುಲಭವಾಗಿ ವಿವರಿಸಿ.",
                 "ಗ್ರಾಹಕರ ಅಭಿಪ್ರಾಯಗಳನ್ನು ವಿಶ್ಲೇಷಿಸಿ ಮುಖ್ಯ ಸಮಸ್ಯೆಗಳನ್ನು ಪಟ್ಟಿ ಮಾಡಿ.",
                 "ಟೊಮ್ಯಾಟೊ ಬೆಳೆಗೆ ಉತ್ತಮ ನೀರಾವರಿ ವೇಳಾಪಟ್ಟಿಯನ್ನು ಸೂಚಿಸಿ.",
                 "ಬೆಂಗಳೂರಿನಿಂದ ಮೈಸೂರಿಗೆ ರೈಲು ಮತ್ತು ಬಸ್ ಪ್ರಯಾಣವನ್ನು ಹೋಲಿಸಿ.",
                 "ಸಭೆಯ ಟಿಪ್ಪಣಿಗಳ ಸಂಕ್ಷಿಪ್ತ ಸಾರಾಂಶ ಕೊಡಿ.",
                 "CSV ಫೈಲ್‌ನಿಂದ ಪುನರಾವರ್ತಿತ ಸಾಲುಗಳನ್ನು ತೆಗೆಯುವ ಪೈಥಾನ್ ಕೋಡ್ ಬರೆಯಿರಿ.",
                 "ಉತ್ಪನ್ನ ಬಿಡುಗಡೆಗೆ ಬೇಕಾದ ಕೆಲಸಗಳ ಪಟ್ಟಿ ಮಾಡಿ."],
        "cons": ["ಉತ್ತರದಲ್ಲಿ ನಿಖರವಾಗಿ 5 ಅಂಶಗಳು ಇರಬೇಕು.",
                 "ಉತ್ತರ 150 ಪದಗಳಿಗಿಂತ ಕಡಿಮೆ ಇರಲಿ.",
                 "ಕೊನೆಯ ದಿನಾಂಕ 15 ಡಿಸೆಂಬರ್ 2026.",
                 "ಕನ್ನಡದಲ್ಲಿ ಮಾತ್ರ ಉತ್ತರಿಸಿ.",
                 "ಒಟ್ಟು ವೆಚ್ಚ ₹25,000 ಎಂದು ಉಲ್ಲೇಖಿಸಿ."],
        "neg": ["ಗ್ರಾಹಕರ ಹೆಸರುಗಳನ್ನು ಸೇರಿಸಬೇಡಿ.",
                "ತಾಂತ್ರಿಕ ಪದಗಳನ್ನು ಬಳಸಬೇಡಿ.",
                "ಆಂತರಿಕ ಬೆಲೆಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಬೇಡಿ.",
                "ಒಂದು ಪುಟಕ್ಕಿಂತ ಹೆಚ್ಚು ಬರೆಯಬೇಡಿ."],
        "fmt": ["ಉತ್ತರವನ್ನು ಎರಡು ಕಾಲಮ್‌ಗಳ ಕೋಷ್ಟಕದಲ್ಲಿ ಕೊಡಿ.",
                "ಹಂತಗಳಿಗೆ ಸಂಖ್ಯೆಯ ಪಟ್ಟಿ ಬಳಸಿ.",
                "ಉತ್ತರವನ್ನು ಔಪಚಾರಿಕ ಶೈಲಿಯಲ್ಲಿ ಬರೆಯಿರಿ."],
        "near": [("ಗ್ರಾಹಕರ ಹೆಸರುಗಳನ್ನು ಸೇರಿಸಬೇಡಿ.", "ನೆನಪಿಡಿ, ಯಾವುದೇ ಗ್ರಾಹಕರ ಹೆಸರು ಉತ್ತರದಲ್ಲಿ ಬರಬಾರದು."),
                 ("ಕನ್ನಡದಲ್ಲಿ ಮಾತ್ರ ಉತ್ತರಿಸಿ.", "ಮತ್ತೊಮ್ಮೆ ಹೇಳುತ್ತೇನೆ, ಉತ್ತರ ಕನ್ನಡದಲ್ಲೇ ಇರಬೇಕು.")],
        "roman": ["Namaskara!  Ee report na summary kodi.  Customer hesaru haakabedi.  Customer hesaru haakabedi.  Kannadadalli matra uttarisi.",
                  "Dayavittu   Python code bareyiri, CSV file inda duplicate rows tegeyalu. Explanation beda. Explanation beda.",
                  "Please ee meeting notes na 5 points alli summary maadi. Deadline 15 December. Names haakabedi. Please ee meeting notes na 5 points alli summary maadi.",
                  "Bengaluru inda Mysuru ge train mattu bus compare maadi!!!   Table format alli kodi. Price ₹500 kinta kammi irali."],
    },
    "hi": {
        "open": ["नमस्ते! मुझे एक बहुत ज़रूरी काम में आपकी मदद चाहिए।",
                 "कृपया नीचे दिए गए काम को ध्यान से करें।",
                 "मैं एक प्रोजेक्ट पर काम कर रहा हूँ और मुझे आपकी सहायता की आवश्यकता है।"],
        "task": ["इस तिमाही की बिक्री रिपोर्ट का सारांश सरल भाषा में लिखें।",
                 "नए छात्रों को प्रकाश संश्लेषण आसान तरीके से समझाइए।",
                 "ग्राहकों की प्रतिक्रिया का विश्लेषण करें और मुख्य समस्याएँ बताइए।",
                 "टमाटर की फसल के लिए सबसे अच्छा सिंचाई कार्यक्रम सुझाइए।",
                 "बेंगलुरु से मैसूरु तक ट्रेन और बस यात्रा की तुलना करें।",
                 "बैठक के नोट्स का संक्षिप्त सारांश दीजिए।",
                 "CSV फ़ाइल से दोहराई गई पंक्तियाँ हटाने वाला पायथन कोड लिखिए।",
                 "उत्पाद लॉन्च के लिए ज़रूरी कामों की सूची बनाइए।"],
        "cons": ["उत्तर में ठीक 5 बिंदु होने चाहिए।",
                 "उत्तर 150 शब्दों से कम होना चाहिए।",
                 "अंतिम तिथि 15 दिसंबर 2026 है।",
                 "केवल हिंदी में उत्तर दें।",
                 "कुल लागत ₹25,000 का उल्लेख करें।"],
        "neg": ["ग्राहकों के नाम शामिल न करें।",
                "तकनीकी शब्दों का प्रयोग मत करें।",
                "आंतरिक कीमतें साझा न करें।",
                "एक पेज से ज़्यादा न लिखें।"],
        "fmt": ["उत्तर को दो कॉलम वाली तालिका में दें।",
                "चरणों के लिए क्रमांकित सूची का उपयोग करें।",
                "उत्तर औपचारिक शैली में लिखें।"],
        "near": [("ग्राहकों के नाम शामिल न करें।", "याद रखें, उत्तर में कहीं भी किसी ग्राहक का नाम नहीं आना चाहिए।"),
                 ("केवल हिंदी में उत्तर दें।", "फिर से कह रहा हूँ, जवाब सिर्फ़ हिंदी में होना चाहिए।")],
        "roman": ["Namaste!  Is report ka summary do.  Customer ke naam mat daalo.  Customer ke naam mat daalo.  Sirf Hindi mein jawab do.",
                  "Kripya   Python code likho jo CSV file se duplicate rows hataye. Explanation nahi chahiye. Explanation nahi chahiye.",
                  "Please meeting notes ka 5 points mein summary banao. Deadline 15 December hai. Naam mat likhna. Please meeting notes ka 5 points mein summary banao.",
                  "Bengaluru se Mysuru train aur bus compare karo!!!   Table format mein do. Price ₹500 se kam ho."],
    },
    "ta": {
        "open": ["வணக்கம்! எனக்கு ஒரு முக்கியமான வேலையில் உங்கள் உதவி தேவை.",
                 "தயவுசெய்து கீழே உள்ள வேலையை கவனமாக செய்யுங்கள்.",
                 "நான் ஒரு திட்டத்தில் வேலை செய்கிறேன், அதற்கு உங்கள் உதவி தேவை."],
        "task": ["இந்த காலாண்டு விற்பனை அறிக்கையின் சுருக்கத்தை எளிமையாக எழுதுங்கள்.",
                 "புதிய மாணவர்களுக்கு ஒளிச்சேர்க்கையை எளிதாக விளக்குங்கள்.",
                 "வாடிக்கையாளர் கருத்துகளை பகுப்பாய்வு செய்து முக்கிய பிரச்சினைகளை பட்டியலிடுங்கள்.",
                 "தக்காளி பயிருக்கு சிறந்த நீர்ப்பாசன அட்டவணையை பரிந்துரைக்கவும்.",
                 "பெங்களூருவிலிருந்து மைசூருக்கு ரயில் மற்றும் பேருந்து பயணத்தை ஒப்பிடுங்கள்.",
                 "கூட்டக் குறிப்புகளின் சுருக்கமான சாராம்சத்தை கொடுங்கள்.",
                 "CSV கோப்பிலிருந்து மீண்டும் வரும் வரிசைகளை நீக்கும் பைத்தான் குறியீட்டை எழுதுங்கள்.",
                 "தயாரிப்பு வெளியீட்டுக்கு தேவையான பணிகளை பட்டியலிடுங்கள்."],
        "cons": ["பதிலில் சரியாக 5 குறிப்புகள் இருக்க வேண்டும்.",
                 "பதில் 150 சொற்களுக்குள் இருக்க வேண்டும்.",
                 "கடைசி தேதி 15 டிசம்பர் 2026.",
                 "தமிழில் மட்டும் பதில் அளிக்கவும்.",
                 "மொத்த செலவு ₹25,000 என்று குறிப்பிடுங்கள்."],
        "neg": ["வாடிக்கையாளர் பெயர்களை சேர்க்க வேண்டாம்.",
                "தொழில்நுட்ப சொற்களை பயன்படுத்த வேண்டாம்.",
                "உள் விலைகளை பகிர வேண்டாம்.",
                "ஒரு பக்கத்திற்கு மேல் எழுத வேண்டாம்."],
        "fmt": ["பதிலை இரண்டு நெடுவரிசை அட்டவணையாக கொடுங்கள்.",
                "படிகளுக்கு எண்ணிட்ட பட்டியலை பயன்படுத்துங்கள்.",
                "பதிலை முறையான நடையில் எழுதுங்கள்."],
        "near": [("வாடிக்கையாளர் பெயர்களை சேர்க்க வேண்டாம்.", "நினைவில் கொள்ளுங்கள், எந்த வாடிக்கையாளர் பெயரும் பதிலில் வரக்கூடாது."),
                 ("தமிழில் மட்டும் பதில் அளிக்கவும்.", "மீண்டும் சொல்கிறேன், பதில் தமிழிலேயே இருக்க வேண்டும்.")],
        "roman": ["Vanakkam!  Indha report-oda summary kodunga.  Customer peyar podaadheenga.  Customer peyar podaadheenga.  Tamil-la mattum badhil sollunga.",
                  "Thayavuseydhu   Python code ezhudhunga, CSV file-la irundhu duplicate rows neekka. Explanation vendaam. Explanation vendaam.",
                  "Please meeting notes-ai 5 points-la summary pannunga. Deadline 15 December. Peyar podaadheenga. Please meeting notes-ai 5 points-la summary pannunga.",
                  "Bengaluru-la irundhu Mysuru-ku train and bus compare pannunga!!!   Table format-la kodunga. Price ₹500-ku kammiya irukkanum."],
    },
    "te": {
        "open": ["నమస్కారం! నాకు ఒక ముఖ్యమైన పనిలో మీ సహాయం కావాలి.",
                 "దయచేసి కింది పనిని శ్రద్ధగా చేయండి.",
                 "నేను ఒక ప్రాజెక్ట్‌పై పని చేస్తున్నాను, దానికి మీ సహాయం కావాలి."],
        "task": ["ఈ త్రైమాసిక అమ్మకాల నివేదిక సారాంశాన్ని సరళంగా రాయండి.",
                 "కొత్త విద్యార్థులకు కిరణజన్య సంయోగక్రియను సులభంగా వివరించండి.",
                 "కస్టమర్ అభిప్రాయాలను విశ్లేషించి ముఖ్య సమస్యలను జాబితా చేయండి.",
                 "టమాటా పంటకు మంచి నీటిపారుదల షెడ్యూల్ సూచించండి.",
                 "బెంగళూరు నుండి మైసూరుకు రైలు మరియు బస్సు ప్రయాణాన్ని పోల్చండి.",
                 "సమావేశ గమనికల సంక్షిప్త సారాంశం ఇవ్వండి.",
                 "CSV ఫైల్ నుండి పునరావృత వరుసలను తొలగించే పైథాన్ కోడ్ రాయండి.",
                 "ఉత్పత్తి విడుదలకు కావలసిన పనుల జాబితా తయారు చేయండి."],
        "cons": ["సమాధానంలో సరిగ్గా 5 అంశాలు ఉండాలి.",
                 "సమాధానం 150 పదాలకు మించకూడదు.",
                 "చివరి తేదీ 15 డిసెంబర్ 2026.",
                 "తెలుగులో మాత్రమే సమాధానం ఇవ్వండి.",
                 "మొత్తం ఖర్చు ₹25,000 అని పేర్కొనండి."],
        "neg": ["కస్టమర్ పేర్లను చేర్చవద్దు.",
                "సాంకేతిక పదాలను ఉపయోగించవద్దు.",
                "అంతర్గత ధరలను పంచుకోవద్దు.",
                "ఒక పేజీ కంటే ఎక్కువ రాయవద్దు."],
        "fmt": ["సమాధానాన్ని రెండు నిలువు వరుసల పట్టికలో ఇవ్వండి.",
                "దశలకు సంఖ్యల జాబితా ఉపయోగించండి.",
                "సమాధానాన్ని అధికారిక శైలిలో రాయండి."],
        "near": [("కస్టమర్ పేర్లను చేర్చవద్దు.", "గుర్తుంచుకోండి, సమాధానంలో ఏ కస్టమర్ పేరు కూడా రాకూడదు."),
                 ("తెలుగులో మాత్రమే సమాధానం ఇవ్వండి.", "మళ్ళీ చెబుతున్నాను, సమాధానం తెలుగులోనే ఉండాలి.")],
        "roman": ["Namaskaram!  Ee report summary ivvandi.  Customer perlu cherchavaddu.  Customer perlu cherchavaddu.  Telugu lo matrame samadhanam ivvandi.",
                  "Dayachesi   Python code rayandi, CSV file nundi duplicate rows teseyadaniki. Explanation vaddu. Explanation vaddu.",
                  "Please meeting notes ni 5 points lo summary cheyandi. Deadline 15 December. Perlu rayavaddu. Please meeting notes ni 5 points lo summary cheyandi.",
                  "Bengaluru nundi Mysuru ki train mariyu bus compare cheyandi!!!   Table format lo ivvandi. Price ₹500 kanna takkuva undali."],
    },
}

REPEAT_PLAN = ["exact", "exact", "near", "none"]   # cycled over the 16 composed prompts


def compose(lang: str, i: int) -> tuple[str, str, str]:
    b = BANK[lang]
    plan = REPEAT_PLAN[i % 4]
    task = b["task"][i % len(b["task"])]
    cons = [b["cons"][i % 5], b["cons"][(i + 2) % 5]]
    neg = b["neg"][i % 4]
    fmt = b["fmt"][i % 3]
    parts = [b["open"][i % 3], task, *cons, neg, fmt]
    if plan == "exact":
        parts.append([neg, cons[0]][i % 2])                       # exact repeat of a detail-bearing line
    elif plan == "near":
        a, nb = b["near"][i % 2]
        if a not in parts:
            parts.insert(3, a)
        parts.append(nb)                                          # same instruction, other words
    sep = "  " if i % 3 == 0 else " "                             # some formatting noise
    text = sep.join(parts)
    if i % 5 == 0:
        text = text.replace(".", "!!!", 1) if lang == "en" else text + "\n\n\n"
    return text, plan, CATS[i % len(CATS)]


def main() -> None:
    rows = []
    for lang in ("en", "kn", "hi", "ta", "te"):
        n_native = 20 if lang == "en" else 16
        for i in range(n_native):
            text, plan, cat = compose(lang, i)
            rows.append({"id": f"{lang}_verbose-{i + 1:02d}", "variant": f"{lang}_verbose", "language": lang,
                         "script": SCRIPT[lang], "category": cat, "repeat": plan, "text": text,
                         "provenance": "synthetic_ai_drafted", "review_status": "pending_review"})
        for j, text in enumerate(BANK[lang].get("roman", [])):
            rows.append({"id": f"{lang}_roman_verbose-{j + 1:02d}", "variant": f"{lang}_roman",
                         "language": lang, "script": "Latn", "category": "code_mixed" if j else "assistant",
                         "repeat": "exact" if j < 3 else "none", "text": text,
                         "provenance": "synthetic_ai_drafted", "review_status": "pending_review"})
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} prompts -> {OUT}")


if __name__ == "__main__":
    main()
