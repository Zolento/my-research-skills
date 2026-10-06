# AGENTS.md — Rules for skill development in this repository

This repository holds agent skills. Each top-level directory is one skill.
The `main` branch holds installable skills only.

These rules apply to every skill in this repository. Read them before you change
any skill.

This file is a development file. Keep it on a development branch.
Do not merge this file into `main`.

## Rule 1 — Keep development files off `main`

`main` carries the installable product. A development file is not part of a skill.

Development files include design specifications, verification records, review
reports, and the notes that support them.

- Put a development file on a development branch.
- Do not put a development file on `main`.
- Remove the file from `main` before the release.

A root `docs/` directory once reached `main` this way. The content was wrong
for `main`.

## Rule 2 — Read the branch content before the merge

A fast-forward merge keeps a linear history. A fast-forward merge does not check
whether the content belongs on the target branch.

Before the merge, run `git ls-tree -r --name-only <branch>` on the source branch.
Read the list. Ask one question for each path. Must this path go to the target branch?

`--ff-only` guarantees the history shape. It does not guarantee the content.

## Rule 3 — Run the workflow to test the workflow

A static check finds an edit fault. A static check does not find a workflow that
cannot run.

A rule can require an object. No stage can produce that object. Every table check
passes. The first real execution fails.

For each stage:

1. Read the document as an instruction.
2. Build the output of the stage.
3. Feed the output to the validator.
4. Record the exit code.

This method found four defects in one skill. Ten rounds of table checks missed
all four.

## Rule 4 — Change a rule and its copies together

One rule appears in several places. Examples: the rule table, the policy file,
the template, and the skill entry point.

A stale copy makes a false statement. One rule file said "no new hard rule beyond
the current set". The same round added two rules.

- Find every copy of the rule before the change.
- Update every copy in the same commit.
- Add a check that compares the copies.

## Rule 5 — Add one check for each new fault class

A reader misses the fault. A script does not. Keep one check for each class of
fault that you find.

Typical checks for a skill:

- Table integrity: column counts, file names, and row names.
- Reference integrity: each identifier points to an object that exists.
- Carrier completeness: each field in a write table has a place in the template.
- Packaged links: each relative link stays inside the skill directory.
- Frontmatter: the required keys and the trigger words are present.
- Section parity: the specification, the template, and the generator agree.

## Rule 6 — Keep one writer on one file

Two writers on one file corrupt the result. One writer stopped in the middle.
The file stayed half-finished.

- Give each writer a different file.
- Stop all writers before a review.
- A review reads. A review does not change the reviewed file.
- Send the findings in a message before you write the report file.
  An agent can finish the analysis and then fail at the file write.

## Rule 7 — Keep the discovery keys in the frontmatter

The `SKILL.md` frontmatter is the discovery surface. The installer reads it.

A large rewrite can drop three items: the argument hint, the version, and the
trigger words. The skill still runs. Fewer users can find it.

- Keep the name, the description, the argument hint, and the version.
- Keep the trigger words.
- Compare the new frontmatter with the last release.

## Rule 8 — Put a known gap in a test, not in prose

A gap in prose looks like a gap that you accepted. A gap in a test stays visible.

- Mark the gap with `skipTest`.
- Write the reason in the test.
- Do not weaken an assertion to make the suite green.

## Rule 9 — Write for the machine reader

Another agent reads your text. A second meaning in one sentence costs that agent
a wrong action.

- Use the active voice.
- Use one instruction in each sentence.
- Use 20 words or fewer in an instruction. Use 25 words or fewer in a description.
- Use one word for one action. Reuse that word. Do not rotate synonyms.
- Do not use a semicolon.
- Do not use a phrasal verb. Use the single plain verb.
- Keep the subject, the verb, and the article. Do not drop them.
- Keep the strength of every hedge. Do not turn "may fail" into "fails".
- Keep the numbers, the conditions, and the scope.

## Checklist before the release

1. For each skill that you changed, run its test suite.
2. For each skill that you changed, run its validator self-test.
3. Run the link check for each skill.
4. Run the deprecated-word scan.
5. Run the controlled-language linter.
6. Apply Rule 2. Compare the source branch with the target branch.
7. Read `git status`. The tree must be clean.
