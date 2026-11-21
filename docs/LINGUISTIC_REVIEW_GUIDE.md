# Linguistic review guide

## For reviewers (no coding needed)

REDUTAX shortens AI prompts without changing their meaning. To do that safely in **Kannada, Hindi, Tamil and Telugu**, it needs word lists that a speaker of each language has checked.

An AI assistant drafted every entry. **None has been checked by a native speaker yet.** Your job is to approve, reject or correct them.

### What you will see

Each entry has:
- the expression in its script;
- its English meaning;
- a category;
- where it applies, the original wording and a proposed shorter wording.

| Category | What it is for | What to check |
|---|---|---|
| Negation | Words like ಬೇಡ, मत, வேண்டாம், వద్దు | Is it really a "not / don't" word or ending? |
| Condition | "if / unless / otherwise / until" words and endings (ಬಂದರೆ, अगर, வந்தால், వస్తే) | Does it really express a condition? |
| Constraint | "only / must / at least / at most / always / all" | Does it restrict or oblige? |
| Question | "what / who / when / where / why / how" | Is it a question word? |
| Names & titles | ಶ್ರೀ, श्री, திரு, శ్రీ … (the next word is treated as a name) | Is it a title used before names? |
| Numbers, units & dates | Number words, units (kg, litre, day), months, today/tomorrow | Correct number, unit or date? Common spellings? |
| Formal / informal | Polite words and pronouns (ನೀವು/ನೀನು, आप/तुम, நீங்கள்/நீ, మీరు/నువ్వు) | Correct level of politeness? |
| Redundant expression | Wording with a repeated idea and a shorter version | Does the shorter version mean **exactly** the same? |
| Shorter wording | Longer phrasings with a shorter alternative | Same meaning? Same tone? |
| Romanized | The same words written in English letters (e.g. *kripya*, *beda*, *vaddu*) | Is this how people really write it? |

### How to decide

| Choose | When |
|---|---|
| **Approve** | The entry is correct as written. |
| **Reject** | It is wrong, misleading, or too ambiguous to use. |
| **Correct** | It is nearly right. Type the correct expression, shorter wording or English meaning. |

For shorter-wording entries, also answer three questions:
1. **Keeps the meaning?**
2. **Changes tone or politeness?**
3. **Safe to apply without asking the user?**

A shorter wording is used automatically **only** if you approve it **and** answer yes / no / yes. Otherwise it is only ever shown as a suggestion that the user must approve.

Add a note whenever something is uncertain, for example "only in formal writing" or "means 'but' in speech".

### Two ways to review

1. **Review screen.** Open REDUTAX → **Research → Linguistic Review**.
   1. Choose your language.
   2. Type your name.
   3. Review the entries; your decisions are saved in your browser as drafts.
   4. Click **Export decisions (JSON)** and send the file to the team.
2. **Spreadsheet.** Ask the team for your language's sheet. In Excel or Google Sheets, fill only the columns in CAPITALS:
   - `YOUR_DECISION`: approve / reject / correct;
   - the `CORRECTED_…` columns;
   - `PRESERVES_MEANING`, `CHANGES_TONE`, `SAFE_FOR_AUTOMATIC_USE`: yes / no;
   - `NOTES`.

   Then send it back.

Nothing changes in REDUTAX until the team merges your file. Your name is recorded with every decision.

## For the team: merging decisions

```bash
# spreadsheet for a reviewer
python research/scripts/export_review_sheet.py --language kn --out kannada_review.csv

# check a returned file without writing anything
python research/scripts/apply_review_decisions.py --decisions kannada_review.json --reviewer "Name" --dry-run
python research/scripts/apply_review_decisions.py --decisions kannada_review.csv --language kn --reviewer "Name" --dry-run

# merge (then run the tests and commit with team approval)
python research/scripts/apply_review_decisions.py --decisions kannada_review.json --reviewer "Name"
cd backend && pytest tests/test_linguistic_review.py tests/test_indic_adversarial.py
```

How the merge works:
- It changes only the `review: {…}` part of each decided entry, so the git diff shows exactly what the reviewer decided.
- It refuses a missing reviewer name, unknown ids, and "correct" without a correction.
- It validates the result with the backend loader before writing.

### What an approval unlocks

| Approved | Effect |
|---|---|
| Detection entries for a language (negation, conditions, constraints, questions, numbers, titles, formality) | Once **all** detection entries of a language are approved, its word lists count as reviewed. Word changes in that language are then no longer flagged as "pending word lists" by the meaning check. |
| Negation forms that mirror `backend/app/core/lexicons/negation.yaml` | The team also sets that list's `review_status: reviewed` (and `reviewed_by`). This step is manual and deliberate. |
| A shorter wording with keeps-meaning = yes, changes-tone = no, safe = yes | Applied automatically in **balanced** mode, but only once that language's detection lists are also reviewed. Until then the meaning check cannot vouch for words in that language, so it stays a suggestion. |
| A shorter wording that changes tone, or is not safe for automatic use | Always a suggestion that needs the user's approval. |
| English phrase-list entries (`en.yaml` in the review data) | The signed approval of an entry **is** the team review for that entry, so it is applied without editing `phrases/en.yaml`. That developer list stays `developer_curated`, and its unapproved entries remain aggressive-mode suggestions. The four politeness-removing entries stay suggestions even if approved. |

Rejected entries are never used.
