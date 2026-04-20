# Grading Rubric

## Verdicts

### match
The finding describes the **same underlying issue** as an expected finding, regardless of wording differences. The rule ID, file, and approximate location should align. Severity and category must also match for a full match.

### partial_match
The finding addresses a **related aspect** of an expected issue but differs in severity or category. For example, a finding that identifies the same SQL injection but classifies it as WARN instead of BUG, or as "correctness" instead of "security".

### novel_valid
The finding describes a **real, actionable code issue** that is NOT in the expected set. The issue would be worth flagging in a real code review. Examples: a genuine performance concern, a missing error handler, or a real security issue that the expected set did not anticipate.

### no_match
The finding is **noise** -- not a real issue, too vague to be actionable, or describes something that is intentional/correct in context. False positives fall into this category.

## Confidence Levels

- **high**: The verdict is clear-cut with strong evidence.
- **medium**: The verdict is likely correct but there is some ambiguity.
- **low**: The verdict is uncertain; the finding is borderline.

## Matching Rules

1. When assigning `match` or `partial_match`, you MUST set `matched_expected_id` to the ID of the expected finding that matches.
2. When assigning `novel_valid` or `no_match`, set `matched_expected_id` to null.
3. Each expected finding can be matched at most once. If multiple actual findings could match the same expected finding, only the closest match should claim it.
