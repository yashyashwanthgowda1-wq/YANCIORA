# Transliteration spot check (native speakers)

Generated from the actual output of `indic_transliteration` 2.3.82 via `POST /api/script-variants`
(translit_v1). **Nothing here is approved yet.** For each row, mark whether the Romanized text
is an acceptable transliteration under the named scheme, and note problems.

Known issues found by tests (please confirm):
- Tamil: consonants are given Sanskrit-style values (த → `dh`, ட → `ḍh`), not standard Tamil romanization.
- Hindi + ITRANS-Dravidian: आऊंगा → `AUMgA`, which converts back as ॐगा (flagged lossy).
- Hindi + Baraha: chandrabindu (ँ) does not round-trip (flagged lossy).
- Hindi: inherent vowel is written (`kala` for कल), unlike everyday typing (`kal`).

## Kannada

| Native | ISO 15919 | baraha | Round trip (ISO / baraha) | OK? | Reviewer notes |
|---|---|---|---|---|---|
| ಕನ್ನಡ | `kannaḍa` | `kannaDa` | lossless / lossless | ☐ | |
| ನಾನು ನಾಳೆ ಬರುವುದಿಲ್ಲ | `nānu nāḷe baruvudilla` | `nAnu nALe baruvudilla` | lossless / lossless | ☐ | |
| ಬೆಳಿಗ್ಗೆ ಹೊಸ ಪುಸ್ತಕ | `beḷigge hosa pustaka` | `beLigge hosa pustaka` | lossless / lossless | ☐ | |
| ದಯವಿಟ್ಟು ವರದಿಯನ್ನು ಕಳುಹಿಸಿ | `dayaviṭṭu varadiyannu kaḷuhisi` | `dayaviTTu varadiyannu kaLuhisi` | lossless / lossless | ☐ | |
| ಕ್ಷಮಿಸಿ ಶ್ರೀ | `kṣamisi śrī` | `kShamisi shrI` | lossless / lossless | ☐ | |

## Hindi

| Native | ISO 15919 | itrans_dravidian | Round trip (ISO / itrans_dravidian) | OK? | Reviewer notes |
|---|---|---|---|---|---|
| हिंदी | `hiṁdī` | `hiMdI` | lossless / lossless | ☐ | |
| मैं कल नहीं आऊँगा | `maiṁ kala nahīṁ āūm̐gā` | `maiM kala nahIM AU.NgA` | lossless / lossless | ☐ | |
| कृपया रिपोर्ट भेजें | `kr̥payā ripōrṭa bhējēṁ` | `kRRipayA ripOrTa bhEjEM` | lossless / lossless | ☐ | |
| आऊंगा | `āūṁgā` | `AUMgA` | lossless / LOSSY | ☐ | |
| क्षमा श्री | `kṣamā śrī` | `kShamA shrI` | lossless / lossless | ☐ | |

## Tamil

| Native | ISO 15919 | itrans_dravidian | Round trip (ISO / itrans_dravidian) | OK? | Reviewer notes |
|---|---|---|---|---|---|
| தமிழ் | `dhamiḻ` | `dhamizh` | lossless / lossless | ☐ | |
| நான் நாளை வரமாட்டேன் | `nāṉ nāḷai varamāḍhḍhēṉ` | `nAn2 nALai varamADhDhEn2` | lossless / lossless | ☐ | |
| தயவுசெய்து அனுப்பவும் | `dhayavujheydhu aṉubhbhavuṁ` | `dhayavujheydhu an2ubhbhavuM` | lossless / lossless | ☐ | |
| சிங்கப்பூர் | `jhiṅghabhbhūr` | `jhi~NghabhbhUr` | lossless / lossless | ☐ | |
| ஒன்று இரண்டு | `oṉṟu iraṇḍhu` | `on2Ru iraNDhu` | lossless / lossless | ☐ | |

## Telugu

| Native | ISO 15919 | itrans_dravidian | Round trip (ISO / itrans_dravidian) | OK? | Reviewer notes |
|---|---|---|---|---|---|
| తెలుగు | `telugu` | `telugu` | lossless / lossless | ☐ | |
| నేను రేపు రాను | `nēnu rēpu rānu` | `nEnu rEpu rAnu` | lossless / lossless | ☐ | |
| దయచేసి పంపండి | `dayacēsi paṁpaṁḍi` | `dayachEsi paMpaMDi` | lossless / lossless | ☐ | |
| క్షమించండి శ్రీ | `kṣamiṁcaṁḍi śrī` | `kShamiMchaMDi shrI` | lossless / lossless | ☐ | |
| ఒకటి రెండు | `okaṭi reṁḍu` | `okaTi reMDu` | lossless / lossless | ☐ | |

Reviewer name / date: ____________________

When a language is approved, record it in `docs/decisions.md` and remove the matching warning
only after the team agrees.
