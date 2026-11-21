# English phrase list — validation matrix (Phase 8)

Date: 2026-11-21 · Optimizer `opt_rules_v3` · meaning check `rules_v5` · tiktoken 0.14.0 (`cl100k_base`, `o200k_base`) · balanced mode, language `en`.

**Status: the English phrase list (`backend/app/optimizer/phrases/en.yaml`) is still INACTIVE** (`review_status: developer_curated`). No entry has team approval. For this matrix each entry was run *as if* approved, in memory only; nothing was activated. Regression test: `backend/tests/test_english_validation.py` (79 tests).

All example sentences were written for this test by an AI assistant (synthetic). Token counts are tokenizer counts under the same encoding before and after, not provider billing.

## Summary for the reviewing team member

| Entry (review id) | Result in 7 contexts | Tokens saved per use (cl100k / o200k) | Recommendation to the reviewer (you decide) |
|---|---|---|---|
| `in order to` (en-red-001) | applied 7/7; all critical details and politeness kept | 2/2 | Can be approved for automatic use if the wording is acceptable |
| `due to the fact that` (en-red-002) | applied 7/7; all critical details and politeness kept | 4/4 | Can be approved for automatic use if the wording is acceptable |
| `at this point in time` (en-red-003) | applied 7/7; all critical details and politeness kept | 4/4 | Can be approved for automatic use if the wording is acceptable |
| `in the event that` (en-red-004) | applied 7/7; all critical details and politeness kept | 3/3 | Can be approved for automatic use if the wording is acceptable |
| `for the purpose of` (en-red-005) | applied 7/7; all critical details and politeness kept | 3/3 | Check: 'for' can be vaguer than 'for the purpose of' |
| `with regard to` (en-red-006) | applied 7/7; all critical details and politeness kept | 2/2 | Can be approved for automatic use if the wording is acceptable |
| `a large number of` (en-red-007) | applied 7/7; all critical details and politeness kept | 3/3 | Can be approved for automatic use if the wording is acceptable |
| `could you please` (en-short-001) | never applied: suggestion in 6 contexts, rejected next to a negation | — (not applied) | Keep suggestion-only: removes a politeness/request frame (changes tone) |
| `can you please` (en-short-002) | never applied: suggestion in 6 contexts, rejected next to a negation | — (not applied) | Keep suggestion-only: removes a politeness/request frame (changes tone) |
| `i would like you to` (en-short-003) | never applied: suggestion in 6 contexts, rejected next to a negation | — (not applied) | Keep suggestion-only: removes a politeness/request frame (changes tone) |
| `i want you to` (en-short-004) | never applied: suggestion in 6 contexts, rejected next to a negation | — (not applied) | Keep suggestion-only: removes a politeness/request frame (changes tone) |

## Finding fixed during this validation

When the shipped list was treated as approved, **"I would like you to …" and "I want you to …" were applied automatically and rated `preserved`**: they turn a polite request into a bare command, but only "please"/"kindly" were registered as politeness markers. The review dataset already marked them `safe_for_auto: false`, but approving `phrases/en.yaml` directly would have bypassed that. Fix: four request frames were added to the English review data as register markers (`en-reg-003` … `en-reg-006`, `pending_review`), so removing one now makes the meaning check ask for review and the optimizer only suggests it.

## Full matrix

| Entry | Context | Original | Result | Optimized (if applied) | Tokens cl100k_base | Tokens o200k_base |
|---|---|---|---|---|---|---|
| `in order to` | negation | Do not restart the server in order to clear the cache. | applied | Do not restart the server to clear the cache. | 12 → 10 | 12 → 10 |
| `in order to` | condition | If the build fails, rerun it in order to get logs. | applied | If the build fails, rerun it to get logs. | 14 → 12 | 14 → 12 |
| `in order to` | constraint | You must log in in order to see the report. | applied | You must log in to see the report. | 11 → 9 | 11 → 9 |
| `in order to` | name | Ask Priya in order to get access. | applied | Ask Priya to get access. | 9 → 7 | 9 → 7 |
| `in order to` | question | Should I wait in order to save money? | applied | Should I wait to save money? | 9 → 7 | 9 → 7 |
| `in order to` | number/date | Send 3 copies by 12 Jan 2026 in order to meet the deadline. | applied | Send 3 copies by 12 Jan 2026 to meet the deadline. | 18 → 16 | 18 → 16 |
| `in order to` | tone | Kindly wait in order to avoid errors. | applied | Kindly wait to avoid errors. | 9 → 7 | 9 → 7 |
| `due to the fact that` | negation | It failed due to the fact that the key was not set. | applied | It failed because the key was not set. | 13 → 9 | 13 → 9 |
| `due to the fact that` | condition | Stop if it fails due to the fact that the disk is full. | applied | Stop if it fails because the disk is full. | 14 → 10 | 14 → 10 |
| `due to the fact that` | constraint | Only retry due to the fact that the API was down. | applied | Only retry because the API was down. | 12 → 8 | 12 → 8 |
| `due to the fact that` | name | Ravi left due to the fact that Meera arrived. | applied | Ravi left because Meera arrived. | 12 → 8 | 12 → 8 |
| `due to the fact that` | question | Was it late due to the fact that it rained? | applied | Was it late because it rained? | 12 → 8 | 12 → 8 |
| `due to the fact that` | number/date | We paid ₹500 due to the fact that the fee rose on 1 March. | applied | We paid ₹500 because the fee rose on 1 March. | 17 → 13 | 17 → 13 |
| `due to the fact that` | tone | Please note it closed due to the fact that it was a holiday. | applied | Please note it closed because it was a holiday. | 14 → 10 | 14 → 10 |
| `at this point in time` | negation | We cannot ship at this point in time. | applied | We cannot ship now. | 9 → 5 | 9 → 5 |
| `at this point in time` | condition | If it is safe at this point in time, deploy. | applied | If it is safe now, deploy. | 12 → 8 | 12 → 8 |
| `at this point in time` | constraint | You must not deploy at this point in time. | applied | You must not deploy now. | 10 → 6 | 10 → 6 |
| `at this point in time` | name | Asha is busy at this point in time. | applied | Asha is busy now. | 10 → 6 | 10 → 6 |
| `at this point in time` | question | Is it ready at this point in time? | applied | Is it ready now? | 9 → 5 | 9 → 5 |
| `at this point in time` | number/date | We have 2 servers at this point in time. | applied | We have 2 servers now. | 11 → 7 | 11 → 7 |
| `at this point in time` | tone | Kindly hold off at this point in time. | applied | Kindly hold off now. | 10 → 6 | 10 → 6 |
| `in the event that` | negation | Do not call in the event that it rains. | applied | Do not call if it rains. | 10 → 7 | 10 → 7 |
| `in the event that` | condition | Call me in the event that the train is late. | applied | Call me if the train is late. | 11 → 8 | 11 → 8 |
| `in the event that` | constraint | You must stop in the event that errors appear. | applied | You must stop if errors appear. | 10 → 7 | 10 → 7 |
| `in the event that` | name | Tell Kiran in the event that it fails. | applied | Tell Kiran if it fails. | 10 → 7 | 10 → 7 |
| `in the event that` | question | What happens in the event that it fails? | applied | What happens if it fails? | 9 → 6 | 9 → 6 |
| `in the event that` | number/date | Pay ₹200 in the event that the bill exceeds 5 kg. | applied | Pay ₹200 if the bill exceeds 5 kg. | 14 → 11 | 14 → 11 |
| `in the event that` | tone | Please inform us in the event that you are late. | applied | Please inform us if you are late. | 11 → 8 | 11 → 8 |
| `for the purpose of` | negation | Do not use it for the purpose of testing. | applied | Do not use it for testing. | 10 → 7 | 10 → 7 |
| `for the purpose of` | condition | If needed for the purpose of audit, keep logs. | applied | If needed for audit, keep logs. | 11 → 8 | 11 → 8 |
| `for the purpose of` | constraint | Use it only for the purpose of research. | applied | Use it only for research. | 9 → 6 | 9 → 6 |
| `for the purpose of` | name | Ravi built it for the purpose of teaching. | applied | Ravi built it for teaching. | 10 → 7 | 10 → 7 |
| `for the purpose of` | question | Is this data for the purpose of training? | applied | Is this data for training? | 9 → 6 | 9 → 6 |
| `for the purpose of` | number/date | Keep 10 copies for the purpose of the 2026 audit. | applied | Keep 10 copies for the 2026 audit. | 14 → 11 | 14 → 11 |
| `for the purpose of` | tone | Kindly use it for the purpose of review. | applied | Kindly use it for review. | 10 → 7 | 10 → 7 |
| `with regard to` | negation | We have no news with regard to the refund. | applied | We have no news about the refund. | 10 → 8 | 10 → 8 |
| `with regard to` | condition | If you have doubts with regard to pricing, ask. | applied | If you have doubts about pricing, ask. | 11 → 9 | 11 → 9 |
| `with regard to` | constraint | You must be careful with regard to privacy. | applied | You must be careful about privacy. | 9 → 7 | 9 → 7 |
| `with regard to` | name | Email Priya with regard to the contract. | applied | Email Priya about the contract. | 9 → 7 | 9 → 7 |
| `with regard to` | question | Any update with regard to the order? | applied | Any update about the order? | 8 → 6 | 8 → 6 |
| `with regard to` | number/date | Call on 5 May with regard to the ₹900 invoice. | applied | Call on 5 May about the ₹900 invoice. | 13 → 11 | 13 → 11 |
| `with regard to` | tone | Please write with regard to the delay. | applied | Please write about the delay. | 8 → 6 | 8 → 6 |
| `a large number of` | negation | Do not send a large number of emails. | applied | Do not send many emails. | 9 → 6 | 9 → 6 |
| `a large number of` | condition | If a large number of users join, scale up. | applied | If many users join, scale up. | 11 → 8 | 11 → 8 |
| `a large number of` | constraint | You must handle a large number of requests. | applied | You must handle many requests. | 9 → 6 | 9 → 6 |
| `a large number of` | name | Ravi got a large number of messages. | applied | Ravi got many messages. | 9 → 6 | 9 → 6 |
| `a large number of` | question | Did a large number of people sign up? | applied | Did many people sign up? | 9 → 6 | 9 → 6 |
| `a large number of` | number/date | By 2026 a large number of farmers used it. | applied | By 2026 many farmers used it. | 12 → 9 | 12 → 9 |
| `a large number of` | tone | Kindly review a large number of files. | applied | Kindly review many files. | 9 → 6 | 9 → 6 |
| `could you please` | negation | Could you please not share this file? | rejected (protected negation) | — | 8 → 8 | 8 → 8 |
| `could you please` | condition | Could you please call if it rains? | suggestion | — | 8 → 8 | 8 → 8 |
| `could you please` | constraint | Could you please reply only in Kannada? | suggestion | — | 9 → 9 | 8 → 8 |
| `could you please` | name | Could you please email Priya? | suggestion | — | 7 → 7 | 7 → 7 |
| `could you please` | question | Could you please check the order? | suggestion | — | 7 → 7 | 7 → 7 |
| `could you please` | number/date | Could you please send 3 files by 12 Jan 2026? | suggestion | — | 15 → 15 | 15 → 15 |
| `could you please` | tone | Could you please write a short poem. | suggestion | — | 8 → 8 | 8 → 8 |
| `can you please` | negation | Can you please not delete the logs? | rejected (protected negation) | — | 8 → 8 | 8 → 8 |
| `can you please` | condition | Can you please retry unless it fails twice? | suggestion | — | 9 → 9 | 9 → 9 |
| `can you please` | constraint | Can you please list at most 5 items? | suggestion | — | 10 → 10 | 10 → 10 |
| `can you please` | name | Can you please call Ravi? | suggestion | — | 7 → 7 | 6 → 6 |
| `can you please` | question | Can you please explain this? | suggestion | — | 6 → 6 | 6 → 6 |
| `can you please` | number/date | Can you please book 2 seats for Monday? | suggestion | — | 10 → 10 | 10 → 10 |
| `can you please` | tone | Can you please list the steps. | suggestion | — | 7 → 7 | 7 → 7 |
| `i would like you to` | negation | I would like you to never share passwords. | rejected (protected negation) | — | 9 → 9 | 9 → 9 |
| `i would like you to` | condition | I would like you to stop if errors appear. | suggestion | — | 10 → 10 | 10 → 10 |
| `i would like you to` | constraint | I would like you to answer only in Hindi. | suggestion | — | 10 → 10 | 10 → 10 |
| `i would like you to` | name | I would like you to thank Meera. | suggestion | — | 9 → 9 | 9 → 9 |
| `i would like you to` | question | I would like you to tell me: is it safe? | suggestion | — | 12 → 12 | 12 → 12 |
| `i would like you to` | number/date | I would like you to send 4 copies by 3 June. | suggestion | — | 14 → 14 | 14 → 14 |
| `i would like you to` | tone | I would like you to explain recursion. | suggestion | — | 8 → 8 | 8 → 8 |
| `i want you to` | negation | I want you to not use slang. | rejected (protected negation) | — | 8 → 8 | 8 → 8 |
| `i want you to` | condition | I want you to wait until the build ends. | suggestion | — | 10 → 10 | 10 → 10 |
| `i want you to` | constraint | I want you to use exactly 3 bullet points. | suggestion | — | 11 → 11 | 11 → 11 |
| `i want you to` | name | I want you to meet Asha. | suggestion | — | 8 → 8 | 8 → 8 |
| `i want you to` | question | I want you to check: does it compile? | suggestion | — | 10 → 10 | 10 → 10 |
| `i want you to` | number/date | I want you to finish 2 tasks by 9 pm. | suggestion | — | 13 → 13 | 13 → 13 |
| `i want you to` | tone | I want you to explain recursion. | suggestion | — | 7 → 7 | 7 → 7 |

## How to approve or reject

Follow `docs/LINGUISTIC_REVIEW_GUIDE.md`: record a decision for each `en-*` entry in the Linguistic Review screen (`/review`, language English) or the spreadsheet export, then merge it with `research/scripts/apply_review_decisions.py`. Approving entries in the review data makes them eligible; `phrases/en.yaml` stays inactive until a team member also sets its `review_status: reviewed` and `reviewed_by`.

## Limits of this matrix

- 77 short, synthetic sentences; real prompts are longer and more varied.
- "Applied and `preserved`" means no rule found a problem. It is not proof that the meaning is identical.
