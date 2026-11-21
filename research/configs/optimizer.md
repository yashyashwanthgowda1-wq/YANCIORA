# Prompt optimizer policy (`opt_rules_v3`)

Implemented in `backend/app/optimizer/rules.py` (rules) and `backend/app/services/optimizer.py`
(pipeline). Phrase lists: `backend/app/optimizer/phrases/*.yaml`. Changing behaviour means
bumping `METHOD_ID`. v2 replaced `opt_rules_v1` on 2026-11-21 (decisions D50–D55).

## opt_rules_v3 (2026-11-21): language-aware wording rules from the review data

- **Source:** wording rules come from the native-speaker review datasets (`backend/app/linguistics/review/*.yaml`, categories `redundant_expression` and `shortening`; D56–D58).
  - Applied automatically in balanced mode only when **approved**, meaning-preserving (`yes`), register-neutral (`no`) and safe for automatic use (`true`).
  - The meaning gate must still say `preserved`. While a language's negation and marker lists are pending review it says `at_risk`, so the edit stays a suggestion.
- **Approved but not safe:** suggestion (`kind: approved_phrase`). This covers rules that change tone or politeness.
- **Pending:** aggressive-mode suggestion (`kind: unreviewed_phrase`), labelled with its entry id.
- **Rejected:** never used.
- **Own language only (D59):** an English phrase rule is never applied to Kannada, Hindi, Tamil or Telugu text, and an Indic list only to text in that language. With `auto`, the Indic scripts present decide; Latin-only text counts as English.
- **Per-edit record:** every accepted, suggested and rejected edit records:
  - `language`;
  - `source` (review entry id);
  - `risk` (`lossless` / `redundancy` / `wording` / `meaning_change`);
  - `approval_required`;
  - `validation` (meaning status or rejecting stage);
  - `tokens_before` / `tokens_after` per tokenizer.
- **Status today:** 0 automatic wording rules (all 399 review entries are pending), so balanced mode changes wording nowhere yet.

## Modes and risk levels

| Mode | Applied automatically | Suggested only (needs approval) | Risk |
|---|---|---|---|
| `safe` | whitespace, invisible characters, repeated punctuation, separator runs | repeated sentences | lossless formatting only |
| `balanced` | safe + exact repeats of an earlier sentence/line **with no critical detail** + **reviewed** phrase lists | repeats that contain details | removes redundancy; an intentional repetition can be removed |
| `aggressive` | same as balanced | + entries of phrase lists **not yet reviewed**, script/transliteration variants | may change meaning; nothing extra applied without approval |

Every response carries `mode_policy` (this text in short form).

## Acceptance policy (team decisions 2026-11-20, extended 2026-11-21)

Every proposed edit goes through, in order:

1. **Protection** — an edit overlapping any critical detail found by Feature 5 (`rules_v3`) →
   `rejected` (`stage: protected`). Phrase-list edits may reword `condition`/`constraint` words;
   the meaning gate then checks the canonical value is unchanged (`in the event that` → `if` passes,
   `only if` → `if` does not).
2. **Overlap** — an edit overlapping an earlier-priority edit → `rejected` (`stage: overlap`).
3. **Tokens** — counted on the exact text under every requested tokenizer (same encoding before and
   after). Must reduce tokens under at least one and increase under none; zero-saving edits are
   rejected (`stage: tokens`).
4. **Meaning gate** (Feature 5, original vs candidate):
   - `preserved` → applied automatically (`accepted`)
   - `at_risk` → **not applied**; returned in `suggestions` with `requires_review: true`
   - `changed` → `rejected` (`stage: meaning`)

   Exception for exact repeats (balanced/aggressive): a repeat with no detected detail is applied
   when the only risk is an unreviewed negation list — every word of the removed copy, including
   any undetected negation, is still in the first copy.

Edits are evaluated one at a time in fixed rule order, left to right (deterministic). At most
200 edits are evaluated per request; the rest are `rejected` with `stage: limit` and a warning.
If nothing is accepted the original string is returned exactly as sent. A final check of the
whole output must pass and no tokenizer may count more tokens, otherwise the original is returned.

## Rules

| Mode | Rule | Edit | Guard |
|---|---|---|---|
| safe+ | `invisible_chars` | remove U+200B, U+00AD, U+2060 | ZWJ U+200D / ZWNJ U+200C kept |
| safe+ | `ws_lines` | 3+ blank lines → 1 blank line; trailing spaces; leading/trailing whitespace of the text | — |
| safe+ | `ws_inline` | 2+ spaces/tabs between non-space characters → 1 space | indentation and line breaks kept |
| safe+ | `punct_repeat` | delete the extra characters: `!!!` → `!`, `??` → `?`, `,,` → `,`, `;;` → `;`, 4+ dots → `...` | first character never touched (protected `?` stays); `...` and `?!` kept |
| safe+ | `separator_runs` (v2) | 4+ of `-` `=` `─` `━` `═` → 3 | not `#` (heading level), `*` (ratings/emphasis), `_` (fill-in blanks), `~` (code fences) |
| balanced+ | `duplicate_sentence` (v2) | a sentence or unpunctuated line (≥ 3 words) that repeats an earlier one anywhere (case- and whitespace-insensitive): delete the later copy and the whitespace before it | applied only with no critical detail inside; otherwise a suggestion naming the details |
| balanced+ | `phrase:<list>` | entries of **reviewed** phrase lists | replacement must be shorter; empty replacement only at sentence start with capitalisation |
| aggressive | `phrase:<list>` (unreviewed) | entries of lists not yet reviewed | suggestion only (`kind: unreviewed_phrase`) |
| aggressive | `script_variant` | whole-text Romanized variants of the optimized text (Feature 6) | suggestion only |

Code inside fences/backticks, URLs, quotes etc. are untouched because they are protected details.

## Measurements in every response

`token_counts` (per tokenizer: before, after, saved, saved_pct — the same encoding for both texts),
`original_chars`, `optimized_chars`, `chars_saved` (characters are not tokens), `language`,
`script`, `mode`, `mode_policy`. Token counts are not provider billing.

## Phrase lists

| List | Status | Applied |
|---|---|---|
| `en` | `developer_curated`, 11 entries | **No** — needs a team member's review; shown as suggestions in aggressive mode |
| `kn`, `hi`, `ta`, `te` | `unreviewed`, empty | No — need native-speaker entries and review |

To activate a list: review every entry, set `review_status: reviewed` and `reviewed_by`.

## Interaction with unreviewed negation lists (rules_v3)

Formatting-only edits (spacing, repeated punctuation, invisible characters, separators) leave the
word content unchanged and are applied in Kannada, Hindi, Tamil and Telugu too. Edits that change
words in Indic text are `at_risk` and stay suggestions until the negation lists are reviewed.

## Evaluation

`research/scripts/run_optimizer_eval.py` (FLORES-200 devtest, evaluation-only licence). Results
and write-up: `research/OPTIMIZER_EVAL_FLORES200.md`.

## Limitations

Savings are tokenizer counts, not provider billing, and on natural Indic text they are small: most
of the token gap comes from how tokenizers split the script. The optimizer does not paraphrase or
summarise. The meaning gate is rule-based (see `meaning_check.md`); `preserved` is not a guarantee
of semantic equivalence.
