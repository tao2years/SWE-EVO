---
name: swebench-case-closer
description: Improve success rate on SWE-bench / SWE-EVO style coding tasks with explicit failing tests or release-note bugfix goals. Use when the task has named target tests, a narrow behavioral contract, or a history of over-exploration, wrong-target edits, validation gaps, or regressions. Focus the agent on target-test-first localization, minimal-path fixes, repeated verification, and early stop-loss when hypotheses drift.
---

# SWE-bench Case Closer

Use this skill for benchmark-style bugfix tasks where success depends on hitting a small, explicit contract rather than exploring broadly.

## Core objective

Turn the task into a tight loop:

1. Read the target tests or reproduction first.
2. Localize the exact failing path.
3. Make the smallest plausible fix.
4. Re-run the exact target verification immediately.
5. Only widen validation after the target path is green.

## Mandatory opening steps

Before editing code:

1. Extract the success contract:
   - release note / user requirement
   - exact `FAIL_TO_PASS` tests
   - constraints such as "do not edit tests"
2. Read the target test file(s) first.
3. Grep the symbols or functions referenced by the failing tests.
4. Identify 1-3 candidate code paths most likely to explain the failure.
5. If possible, run the exact failing test(s) or the smallest reproduction before editing.

Do not start with wide repo exploration if the target tests already point to a narrow path.

## Editing rules

1. Prefer the shortest fix on the direct failing path.
2. Avoid broad refactors, cleanup, or speculative generalization unless the target test forces it.
3. Do not edit tests unless the task explicitly requires it.
4. Do not carry multiple unverified hypotheses at once.
5. If the current hypothesis is weak, gather more evidence before editing.

## Validation loop

After every non-trivial edit:

1. Re-run the exact target test(s) first.
2. If they still fail, inspect the new failure and decide whether:
   - the hypothesis was wrong
   - the patch was incomplete
   - the test points to a neighboring path
3. Only after target tests pass, run the nearest broader verification:
   - selected file
   - nearest module
   - small smoke command

Do not claim success based only on static inspection or broad reasoning.

## Stop-loss rules

Reset your approach if any of these happen:

1. 3 consecutive edits without improving the target test result
2. 8+ tool turns without narrowing the failing path
3. repeated cycling between neighboring files/functions without new evidence
4. broad validation is green but exact target tests are still red

When resetting:

1. Return to the failing test.
2. Reconstruct the exact contract.
3. Re-list the failing stack/path.
4. Pick a different candidate path.

## Final gate

Before finishing, confirm all of the following:

1. Exact target `FAIL_TO_PASS` evidence is green.
2. You did not silently edit tests unless explicitly allowed.
3. The final patch still matches the stated bugfix scope.
4. If broader validation was not run, say so explicitly.

## Failure patterns this skill is designed to suppress

This skill is specifically meant to reduce:

- wrong-target edits
- over-exploration
- hypothesis lock-in
- validation gaps
- F2P overfitting with avoidable regressions
- stopping after a plausible explanation instead of a verified fix
