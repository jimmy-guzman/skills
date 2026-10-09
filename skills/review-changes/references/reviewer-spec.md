# Spec: what was asked for

Read [reviewer-common.md](reviewer-common.md) first.

- Compare the diff with the spec sources and name the line each finding rests on. Unrelated config edits and a refactor riding along with a fix are scope creep.
- Before calling anything missing, check whether unchanged code already does it; read callers only for that check, not routinely. A false "missing" finding costs more to refute than the read would have cost.
- Then check the words against the code: every factual claim the diff adds to docs or comments, and every doc that described behavior the diff changed (grep for it). For a long design or spec doc, grep it for the changed paths and symbols first and read only the matching sections. Docs should be plain, factual, and short; flag filler, restated rationale, and em dashes.
- Check only PR-description claims about behavior the diff changes. A claim the code can't settle (production data, percentages, outcomes elsewhere) is one `left_out` line: "can't verify from code".
- If a linked ticket doesn't describe this change, return one finding saying so and grade against the PR description instead. Don't grade completeness against unrelated items.
- When spec sources disagree with each other (two tickets, or a ticket and a docstring), or wording may just be imprecise, return one finding citing both lines if the code depends on which is right, otherwise one `left_out` line. Don't decide which source is right.
- Answer each question in `verdicts` with the ids of the findings that answer it, or "none" plus one sentence on what you checked. A bare "none" is not an answer.
  - Completeness: is anything the spec asked for not done?
  - Scope: did anything change that the spec didn't ask for?
  - Correctness: does anything built behave unlike the spec?
  - Consistency (only when the diff touches docs or documented behavior): do they disagree?
