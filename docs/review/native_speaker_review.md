# Native-speaker review report

Generated 2026-11-21 from the **actual output** of the REDUTAX backend (`rules_v2`, `opt_rules_v1`,
`translit_v1`). Nothing in this file is approved. Example sentences were written by the developers
and may be wrong — please correct them. Fill in the empty columns; mark **Approve** only after checking.

How to record a decision: put your name and date in *Reviewer*, ✅ or ❌ in *Correct?*, and
describe any fix. When a whole list is approved, the team updates its `review_status` to
`reviewed` and `reviewed_by` (see `research/configs/meaning_check.md`, `optimizer.md`).

Priority order: 1. Tamil transliteration · 2. Negation lists (kn, hi, ta, te) · 3. English phrase list.

## 1. Transliteration spot check

Use `docs/review/transliteration_spot_check.md` (real engine output, 20 rows). **Start with Tamil**:
the engine maps Tamil consonants to Sanskrit-style values (த → `dh`, ட → `ḍh`), which tests flagged.

## 2. Negation word lists

Source: `backend/app/core/lexicons/negation.yaml` (all Indic lists `unreviewed`). *Detected* is what the
checker found in the example sentence. Expected meaning: the sentence is negated by this word.

### Kannada

| List | Form | Match rule | Example sentence (developer-written) | Detected by checker | Expected meaning | Actual meaning (reviewer) | Correct? | Reviewer / decision |
|---|---|---|---|---|---|---|---|---|
| kn-Knda | `ಇಲ್ಲ` | substring | ನನಗೆ ಸಮಯ ಇಲ್ಲ | kn:illa | negation (`kn:illa`) |  | ☐ |  |
| kn-Knda | `ಿಲ್ಲ` | suffix | ನಾನು ನಾಳೆ ಬರುವುದಿಲ್ಲ | kn:illa | negation (`kn:illa`) |  | ☐ |  |
| kn-Knda | `ಬೇಡ` | substring | ಅದು ಬೇಡ | kn:beda | negation (`kn:beda`) |  | ☐ |  |
| kn-Knda | `ಅಲ್ಲ` | substring | ಇದು ನನ್ನದು ಅಲ್ಲ | kn:alla | negation (`kn:alla`) |  | ☐ |  |
| kn-Latn | `illa` | suffix | nange samaya illa | kn:illa | negation (`kn:illa`) |  | ☐ |  |
| kn-Latn | `beda` | word | adu beda | kn:beda | negation (`kn:beda`) |  | ☐ |  |
| kn-Latn | `alla` | word | idu nannadu alla | kn:alla | negation (`kn:alla`) |  | ☐ |  |

Missing negation forms (please list):

| Form | Example | Notes |
|---|---|---|
|  |  |  |

### Hindi

| List | Form | Match rule | Example sentence (developer-written) | Detected by checker | Expected meaning | Actual meaning (reviewer) | Correct? | Reviewer / decision |
|---|---|---|---|---|---|---|---|---|
| hi-Deva | `नहीं` | word | मैं कल नहीं आऊँगा | hi:nahin | negation (`hi:nahin`) |  | ☐ |  |
| hi-Deva | `न` | word | नाम शामिल न करें | hi:na | negation (`hi:na`) |  | ☐ |  |
| hi-Deva | `ना` | word | वहाँ ना जाओ | hi:na | negation (`hi:na`) |  | ☐ |  |
| hi-Deva | `मत` | word | कल मत आना | hi:mat | negation (`hi:mat`) |  | ☐ |  |
| hi-Deva | `बिना` | word | बिना अनुमति प्रवेश न करें | hi:bina, hi:na | negation (`hi:bina`) |  | ☐ |  |
| hi-Latn | `nahi` | word | main kal nahi aaunga | hi:nahin | negation (`hi:nahin`) |  | ☐ |  |
| hi-Latn | `nahin` | word | woh nahin aayega | hi:nahin | negation (`hi:nahin`) |  | ☐ |  |
| hi-Latn | `nhi` | word | mujhe nhi pata | hi:nahin | negation (`hi:nahin`) |  | ☐ |  |
| hi-Latn | `mat` | word | kal mat aana | hi:mat | negation (`hi:mat`) |  | ☐ |  |
| hi-Latn | `bina` | word | bina pooche mat lo | hi:bina, hi:mat | negation (`hi:bina`) |  | ☐ |  |

Missing negation forms (please list):

| Form | Example | Notes |
|---|---|---|
|  |  |  |

### Tamil

| List | Form | Match rule | Example sentence (developer-written) | Detected by checker | Expected meaning | Actual meaning (reviewer) | Correct? | Reviewer / decision |
|---|---|---|---|---|---|---|---|---|
| ta-Taml | `இல்லை` | substring | எனக்கு நேரம் இல்லை | ta:illai | negation (`ta:illai`) |  | ☐ |  |
| ta-Taml | `ில்லை` | substring | அவன் வரவில்லை | ta:illai | negation (`ta:illai`) |  | ☐ |  |
| ta-Taml | `வேண்டாம்` | substring | அது வேண்டாம் | ta:vendam | negation (`ta:vendam`) |  | ☐ |  |
| ta-Taml | `அல்ல` | substring | இது என்னுடையது அல்ல | ta:alla | negation (`ta:alla`) |  | ☐ |  |
| ta-Taml | `ாது` | suffix | என்னால் முடியாது | ta:aadhu | negation (`ta:aadhu`) |  | ☐ |  |
| ta-Latn | `illai` | suffix | enakku neram illai | ta:illai | negation (`ta:illai`) |  | ☐ |  |
| ta-Latn | `illa` | suffix | avan varala illa | ta:illai | negation (`ta:illai`) |  | ☐ |  |
| ta-Latn | `vendam` | word | adhu vendam | ta:vendam | negation (`ta:vendam`) |  | ☐ |  |
| ta-Latn | `venda` | word | adhu venda | ta:vendam | negation (`ta:vendam`) |  | ☐ |  |

Missing negation forms (please list):

| Form | Example | Notes |
|---|---|---|
|  |  |  |

### Telugu

| List | Form | Match rule | Example sentence (developer-written) | Detected by checker | Expected meaning | Actual meaning (reviewer) | Correct? | Reviewer / decision |
|---|---|---|---|---|---|---|---|---|
| te-Telu | `లేదు` | substring | నాకు సమయం లేదు | te:ledu | negation (`te:ledu`) |  | ☐ |  |
| te-Telu | `వద్దు` | substring | అది వద్దు | te:vaddu | negation (`te:vaddu`) |  | ☐ |  |
| te-Telu | `కాదు` | substring | ఇది నాది కాదు | te:kaadu | negation (`te:kaadu`) |  | ☐ |  |
| te-Latn | `ledu` | suffix | naaku samayam ledu | te:ledu | negation (`te:ledu`) |  | ☐ |  |
| te-Latn | `vaddu` | word | adi vaddu | te:vaddu | negation (`te:vaddu`) |  | ☐ |  |
| te-Latn | `kaadu` | word | idi naadi kaadu | te:kaadu | negation (`te:kaadu`) |  | ☐ |  |
| te-Latn | `kadu` | word | idi naadi kadu | te:kaadu | negation (`te:kaadu`) |  | ☐ |  |

Missing negation forms (please list):

| Form | Example | Notes |
|---|---|---|
|  |  |  |

## 3. English phrase list (balanced mode — currently inactive)

Source: `backend/app/optimizer/phrases/en.yaml` (`developer_curated`, not applied). *Output if approved*
is the optimizer's real output with this list treated as reviewed **in memory only for this report**;
token counts are exact counts under each tokenizer (not provider billing).

| Pattern → replacement | Original sentence (developer-written) | Output if approved | cl100k_base | o200k_base | Meaning check | Expected meaning | Actual meaning (reviewer) | Correct? | Reviewer / decision |
|---|---|---|---|---|---|---|---|---|---|
| `in order to` → `to` | Practise daily in order to improve. | Practise daily to improve. | 9→7 | 8→6 | preserved | same request, shorter |  | ☐ |  |
| `due to the fact that` → `because` | The meeting moved due to the fact that the room was booked. | The meeting moved because the room was booked. | 13→9 | 13→9 | preserved | same request, shorter |  | ☐ |  |
| `at this point in time` → `now` | We cannot add users at this point in time. | We cannot add users now. | 10→6 | 10→6 | preserved | same request, shorter |  | ☐ |  |
| `in the event that` → `if` | Call me in the event that the server fails. | Call me if the server fails. | 10→7 | 10→7 | preserved | same request, shorter |  | ☐ |  |
| `for the purpose of` → `for` | This form is for the purpose of registration. | This form is for registration. | 9→6 | 9→6 | preserved | same request, shorter |  | ☐ |  |
| `with regard to` → `about` | I have a question with regard to the invoice. | I have a question about the invoice. | 10→8 | 10→8 | preserved | same request, shorter |  | ☐ |  |
| `a large number of` → `many` | A large number of users signed up. | Many users signed up. | 8→5 | 8→5 | preserved | same request, shorter |  | ☐ |  |
| `could you please` → `(remove, capitalise next)` | Could you please summarise this report? | Summarise this report? | 8→6 | 8→6 | preserved | same request, shorter |  | ☐ |  |
| `can you please` → `(remove, capitalise next)` | Can you please translate this to Kannada? | Translate this to Kannada? | 9→6 | 8→5 | preserved | same request, shorter |  | ☐ |  |
| `i would like you to` → `(remove, capitalise next)` | I would like you to write a short poem. | Write a short poem. | 10→5 | 10→5 | preserved | same request, shorter |  | ☐ |  |
| `i want you to` → `(remove, capitalise next)` | I want you to list three ideas. | List three ideas. | 8→4 | 8→4 | preserved | same request, shorter |  | ☐ |  |

Reviewer name / date: ____________________
