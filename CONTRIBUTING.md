\# Contributing to HOLO-Invariant



Thanks for helping improve HOLO-Invariant.



HOLO is built around a simple development rule:



> Demonstrate a concrete gap, make the smallest change that closes it, and

> verify what the change actually establishes.



Contributions do not need to be large. Small failing tests, reproducible

counterexamples, documentation corrections, benchmark conditions, examples,

and narrowly scoped implementation fixes are all useful.



\## Quick setup



HOLO-Invariant requires Python 3.10 or newer.



Clone the repository:



```bash

git clone https://github.com/Deathburgerz013/HOLO-Invariant.git

cd HOLO-Invariant

```



Install the package and development dependencies:



```bash

python -m pip install -e ".\[dev]"

```



Run the full test suite:



```bash

python -m pytest -q

```



A clean checkout should pass before you begin changing behavior.



\## The contribution loop



Use this sequence whenever possible:



```text

observe

\-> reproduce

\-> write the smallest failing test

\-> identify the existing boundary that owns the behavior

\-> make the smallest supported change

\-> run focused tests

\-> run the full suite

\-> inspect the diff

\-> open a narrowly scoped pull request

```



If the suspected gap cannot be reproduced, stop there.



A failed hypothesis is useful evidence. It is better to discover that the

existing composition already works than to add another abstraction that owns

the same job.



\## Start from current main



Before beginning work:



```bash

git switch main

git pull --ff-only

```



Create a narrowly named branch:



```bash

git switch -c test/example-gap

```



or:



```bash

git switch -c feat/example-boundary

```



or:



```bash

git switch -c docs/example-improvement

```



Keep one independently reviewable problem per branch.



\## Demonstrate the problem first



Implementation changes should normally be justified by a reproducible failure.



Useful evidence includes:



\- a failing unit or composition test;

\- a deterministic benchmark difference;

\- a malformed receipt accepted when it should fail closed;

\- a reconstruction that loses required information;

\- an authority boundary that can be bypassed;

\- a disagreement between independent readers of the same declared state;

\- a documented public interface that does not behave as documented.



Avoid adding production mechanisms only because they seem useful in theory.



A useful question is:



> What exact behavior cannot the current composition express or verify?



If the answer is not demonstrated, implementation may not be warranted yet.



\## Prefer composition tests before new owners



HOLO contains many small contracts that intentionally do different jobs.



Before adding a new module, test whether the existing modules compose correctly.



For example:



```text

proposal

\-> binding

\-> verification

\-> reconstruction

\-> current-state gate

```



If that composition already handles the case correctly, preserve the result

and stop.



Do not create a second owner for behavior an existing contract already owns.



\## Keep authority explicit



A major HOLO invariant is that observation does not silently become authority.



Unless a narrower contract explicitly establishes otherwise:



```text

proposal != verification

storage != truth

observation != authorization

verification != acceptance

historical presence != current applicability

passing one check != global satisfaction

```



New observational or evaluative outputs should not silently gain truth,

acceptance, write authority, or execution authority.



If a contribution changes one of those authorities, that change must be

explicit, narrowly scoped, and independently justified.



\## Preserve uncertainty



Do not collapse unresolved alternatives merely because one interpretation is

ranked higher, sounds more likely, or is preferred by a model.



If multiple interpretations remain compatible with the evidence, preserve

them until discriminating evidence removes one.



Likewise, failure of one proposer to produce a useful next condition does not

prove that no condition exists.



Absence of a proposal is not proof of impossibility.



\## Preserve evidence and history



Raw evidence should remain byte-for-byte unchanged.



Do not incidentally:



\- rewrite historical evidence;

\- normalize raw evidence files;

\- change line endings in unrelated files;

\- replace an original record with its correction;

\- remove contradictory history;

\- manufacture provenance that was not supplied.



Corrections should preserve the original record and bind the relationship

between previous state, evidence, and resulting state.



Hashes establish identity under the declared encoding. They do not establish

truth, relevance, authorship, sufficiency, or authority by themselves.



\## Structured contracts over free-text inference



Prefer explicit structured fields when behavior needs deterministic checking.



Do not make deterministic code pretend to understand arbitrary prose when the

necessary relationship can instead be declared directly.



For example, prefer:



```text

targets\_uncertainty: "<declared uncertainty>"

```



over code that guesses which uncertainty a sentence probably refers to.



Model output may propose structured candidates. Deterministic contracts remain

responsible for validating the declared boundary.



\## AI-assisted contributions



AI-assisted development is welcome.



Treat model output the same way HOLO treats other proposals:



```text

proposal

\-> inspect

\-> test

\-> verify

\-> accept or reject

```



A model may help:



\- study the repository;

\- propose hypotheses;

\- generate candidate tests;

\- draft code;

\- compare outputs;

\- explain failures.



A model response is not evidence that the change is correct.



Generated changes should be reviewed against the same tests, provenance rules,

scope limits, and authority boundaries as human-written changes.



\## Testing



Run the smallest focused test first:



```bash

python -m pytest -q tests/test\_relevant\_boundary.py

```



Then run the relevant composition neighborhood when one exists.



Before opening a pull request, run the complete suite:



```bash

python -m pytest -q

```



Passing tests establish only the cases encoded by those tests.



They do not certify every environment, prove global correctness, or grant

acceptance.



\## Rail-formatted documents



Some HOLO documents use the repository's structured rail grammar.



If you change one, validate it with:



```bash

python -m holosim.spine\_protocol rail-validate path/to/document.md

```



Rail validation checks structure only.



It does not repair, approve, or establish the truth of the document.



\## Before committing



Inspect the working tree:



```bash

git status -sb

```



Check the patch:



```bash

git diff

```



After staging only the intended files:



```bash

git diff --cached --check

git diff --cached

```



Do not bundle unrelated cleanup, formatting, generated files, or speculative

refactors into the same commit.



\## Pull requests



Keep pull requests small enough that another person can determine:



1\. what problem was demonstrated;

2\. what boundary owns the problem;

3\. what changed;

4\. what evidence shows the change works;

5\. what the result does not establish.



A useful pull request structure is:



```markdown

\## Problem demonstrated



Describe the reproducible failure, benchmark difference, or documentation gap.



\## Smallest supported change



Explain what changed and why this boundary owns the behavior.



\## What this does not establish



State important limits explicitly.



\## Verification



Focused:



`...`



Composition:



`...`



Full suite:



`...`



\## Compatibility



\- schemas unchanged or migration documented

\- public API unchanged or release impact documented

\- raw evidence not rewritten

\- no observational output silently gains authority

```



\## Good contribution candidates



If you are new to the project, useful bounded contributions include:



\- reproduce an existing issue;

\- add a missing hostile-case test;

\- test an existing composition without changing production code;

\- add another neutral continuity benchmark baseline;

\- improve a five-minute example;

\- clarify a public API or CLI command;

\- add cross-platform reproduction evidence;

\- test deterministic behavior across fresh processes;

\- identify a stale or misleading documentation claim;

\- produce a minimal counterexample to a declared invariant.



The best first contribution may be a test proving that no production change is

needed.



That is still progress.



\## Scope discipline



Avoid pull requests that combine several architectural ideas only because they

are conceptually related.



Prefer:



```text

one demonstrated gap

\-> one bounded change

\-> one reviewable result

```



instead of:



```text

new abstraction

\+ cleanup

\+ API redesign

\+ scheduler

\+ model integration

\+ documentation rewrite

```



Large changes are easier to justify after their smaller failure boundaries

have been demonstrated independently.



\## Security and safety issues



Do not publish credentials, private keys, access tokens, personal data, or

other secrets in issues, pull requests, fixtures, examples, or logs.



When reporting a security-sensitive problem, minimize unnecessary disclosure

and provide the smallest reproduction needed to establish the issue.



\## Project philosophy



HOLO is designed to preserve inspectable continuity while keeping claims

bounded.



The recurring pattern is:



```text

append

\-> verify

\-> reconstruct

\-> bind

\-> gate

\-> continue or reopen

```



Growth is conditional.



If the current composition already satisfies the demonstrated requirement:



```text

delta = 0

```



Preserve the evidence and stop.



If a reproducible case demonstrates that an existing boundary cannot satisfy a

necessary condition, then the repository has earned a reason to grow.
