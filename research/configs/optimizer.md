# Prompt optimizer policy (`opt_rules_v1`)

Implemented in `backend/app/optimizer/rules.py` (rules) and `backend/app/services/optimizer.py`
(pipeline). Phrase lists: `backend/app/optimizer/phrases/*.yaml`. Changing behaviour means
bumping `METHOD_ID`.

## Acceptance policy (team decisions 2026-11-20)

Every proposed edit goes through, in order:

1. **Protection** — an edit overlapping any critical detail found by Feature 5
   (code, URL, email, quoted text, money, date/time, number, negation, protected term) → `rejected` (`stage: protected`).
2. **Overlap** — an edit overlapping an earlier-priority edit → `rejected` (`stage: overlap`).
3. **Tokens** — counted on the exact text under every requested tokenizer. Must reduce tokens
   under at least one and increase under none; zero-saving edits are rejected (`stage: tokens`).
4. **Meaning gate** (Feature 5, original vs candidate):
   - `preserved` → applied automatically (`accepted`)
   - `at_risk` → **not applied**; returned in `suggestions` with `requires_review: true`
   - `changed` → `rejected` (`stage: meaning`)

Edits are evaluated one at a time in fixed rule order, left to right (deterministic). At most
200 edits are evaluated per request (team decision 2026-11-20); the rest are `rejected` with
`stage: limit` and a warning says how many were not evaluated — nothing is omitted silently.
Running the optimizer again on the output continues with the remaining edits. If nothing is
accepted the original string is returned exactly as sent. A final check of the whole output
must be `preserved` and no tokenizer may count more tokens, otherwise the original is returned.

Duplicate-sentence removals and script changes are **always suggestions**, never applied.

## Rules

| Mode | Rule | Edit | Guard |
|---|---|---|---|
| safe+ | `invisible_chars` | remove U+200B, U+00AD, U+2060 | ZWJ U+200D / ZWNJ U+200C kept |
| safe+ | `ws_lines` | 3+ blank lines → 1 blank line; trailing spaces; leading/trailing whitespace of the text | — |
| safe+ | `ws_inline` | 2+ spaces/tabs between non-space characters → 1 space | indentation and line breaks kept |
| safe+ | `punct_repeat` | `!!`+ → `!`, `??`+ → `?`, `,,`+ → `,`, `;;`+ → `;`, 4+ dots → `...` | `...` and `?!` kept |
| balanced+ | `phrase:<list>` | entries of **reviewed** phrase lists only | replacement must be shorter; empty replacement only at sentence start with capitalisation |
| all | `duplicate_sentence` | back-to-back identical sentences of ≥ 5 words: delete the second | suggestion only |
| aggressive | `script_variant` | whole-text Romanized variants of the optimized text (Feature 6; ISO 15919 + ASCII schemes, distinct texts only) | suggestion only; must save tokens and pass the meaning gate (`changed` → rejected) |

Code inside fences/backticks, URLs, quotes etc. are untouched because they are protected details.

## Phrase lists

| List | Status | Applied |
|---|---|---|
| `en` | `developer_curated` | **No** — needs a team member's review (team decision) |
| `kn`, `hi`, `ta`, `te` | `unreviewed`, empty | No — needs native-speaker entries and review |

To activate a list: review every entry, set `review_status: reviewed` and `reviewed_by`.

## Interaction with unreviewed negation lists

Feature 5 reports `at_risk` for any non-whitespace edit to text whose language has an
unreviewed negation list. So for Kannada, Hindi, Tamil and Telugu today, whitespace fixes are
applied automatically and punctuation/invisible-character fixes become suggestions.

## Performance (measured on the development machine, byte-counting test tokenizer)

| Input | Time |
|---|---|
| 2,000 characters, ~100 edits | ~0.3 s |
| 20,000 characters, 200 edits evaluated (worst case) | ~4.6 s |

The cost grows with edits × text length because every edit gets its own meaning check.

## Limitations

Savings are tokenizer counts, not provider billing, and on Indic text they are usually small:
most of the token gap comes from how tokenizers split the script. The meaning gate is
rule-based (see `meaning_check.md`); `preserved` is not a guarantee of semantic equivalence.
