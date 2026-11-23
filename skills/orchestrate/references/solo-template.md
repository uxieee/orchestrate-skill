# SOLO.md template (one-tab build)

Use this instead of SESSIONS.md when the build has ONE implementer lane (SKILL.md step 2). One tab,
the orchestrator, runs everything: it starts a builder helper per task and a separate QA helper to
review it. Same checks and balances as the multi-tab build: CHECKS.md, the board, QA on the exact
commit in its own copy, the breaker, gates only the user opens.

Copy everything inside the fence into `<DOCS>/SOLO.md` and fill every `{{…}}` (same placeholders as
`sessions-template.md`; `{{LANE}}` is the one lane's name). `grep -n '{{' SOLO.md` must print nothing.

```markdown
# {{NAME}}: one-tab build

One tab, `{{ID}}-orchestrator`, opened in `{{ROOT}}`. It writes no project code. For each task it
starts a **builder helper** (agent `orchestrate-builder`, Haiku) and, when the builder is done, a
separate **QA helper** (agent `orchestrate-qa`, Opus, cannot edit). Helpers get a short brief, not
this conversation; each keeps its own memory, so a FAIL goes back to the same builder and a
re-review to the same QA helper.

    The user <-> {{ID}}-orchestrator  (this tab: assigns, decides, runs gates)
                   |- builder helper, one per task (Haiku; Sonnet after a 3rd FAIL)
                   '- QA helper, one per task (Opus, read-only, its own copy of the code)

## Files
- Plan `{{DOCS}}/plan.md` · spec `{{DOCS}}/spec.md` (optional) · checks `{{DOCS}}/CHECKS.md`
  (`## <task id>` per task: the numbered checks that decide done, each with its evidence)
- Board `{{DOCS}}/state.json` / `STATUS.md`: change it only with `{{BOARD}} <command>`
- Decisions `{{DOCS}}/DECISIONS.md` · helper ids and progress `{{DOCS}}/lanes/{{LANE}}.md` ·
  QA notes `{{DOCS}}/lanes/qa.md` · evidence `{{DOCS}}/evidence/<task id>/`
- Code `{{CODE}}` · QA's copy `{{WT}}/{{ID}}-qa-1`

Precedence: DECISIONS.md beats the plan; the plan wins on how, the spec on what.

## Gates (only the user opens these)
{{GATES, one bullet each; or "None for this project."}}

A gated step runs only in this tab, right after the user types "go" here, and only for the gate they
named. Helpers never run gated steps. When unsure whether something is a gate, treat it as one.

**Standing approvals** (no "go" needed; log each use in DECISIONS.md): {{STANDING APPROVALS or
"None."}} Anything outside their exact scope is a gate. An approval whose scope the user hasn't filled
in yet is not active until they do.

## Orchestrator (this tab)

### Startup (also after a compaction or restart)
1. Read this file, the plan, DECISIONS.md, `lanes/{{LANE}}.md`. Run `{{BOARD}} summary`.
2. If a task is assigned, in progress, qa or failed: resume it (its helper ids are in the lane note;
   message them with SendMessage). A helper that no longer answers: start a new one with the same
   brief plus "continue from commit <sha>; QA's open issues: …".
3. Otherwise start the next task from READY TO START.

### Per task
1. `{{BOARD}} task <id> --state assigned --by {{ID}}-orchestrator`.
2. **Builder.** Agent tool, `subagent_type: "orchestrate-builder"`, background, prompt:
   `Task <id> of {{NAME}}. Read {{DOCS}}/SOLO.md section Builder, then the task in {{DOCS}}/plan.md and its section in {{DOCS}}/CHECKS.md. <Two or three lines: files to read closely, danger zone, any DECISIONS that apply.>`
   Write its agent id in the lane note: `<id> builder <agent id> (haiku)`. Wait for its
   completion notification; don't poll.
3. Builder reports `READY <id> · commit <sha> · …` -> `{{BOARD}} task <id> --state qa --commit <sha> --by {{ID}}-orchestrator`.
   `BLOCKED` -> answer it (Decisions) and SendMessage the answer to the same builder.
4. **QA.** First review of a task: Agent tool, `subagent_type: "orchestrate-qa"`, background,
   prompt: `Review task <id> of {{NAME}} at commit <sha>. Read {{DOCS}}/SOLO.md section QA, then the task in {{DOCS}}/plan.md, its section in {{DOCS}}/CHECKS.md and DECISIONS.md.`
   Write its id in the lane note. Re-reviews: SendMessage the same QA helper
   `Re-review <id> at <new sha> (previous <old sha>).`
5. Verdict:
   - `PASS <sha>`: `{{BOARD}} qa <id> --verdict pass --sha <sha> --by {{ID}}-qa`. Copy the
     follow-ups and QA's notes into `lanes/qa.md`. Next task.
   - `FAIL <sha>` with numbered issues: `{{BOARD}} qa <id> --verdict fail --sha <sha> --issues <n> --classes <classes> --by {{ID}}-qa`,
     copy the issues into `lanes/qa.md`, then SendMessage them, word for word, to the same builder
     (`FAIL round <n>: <issues>. Fix each cause and everything named in "also look for", rerun ALL
     the task's checks, then report READY again.`). Back to step 3.
   - `PLAN PROBLEM`: decide it (Decisions), amend CHECKS.md or the plan by DECISION, and tell both
     helpers.
6. After each step: `{{BOARD}} heartbeat --by {{ID}}-orchestrator` and a one-line lane-note update.

### Optional tasks
When the user says a task isn't required ("we don't need T7 for this", "make it optional"): `{{BOARD}} task <id> --optional --note "user: <their words>" --by {{ID}}-orchestrator`
and a dated DECISIONS.md line. It stays on the board and can still be worked on, but no longer counts
toward progress or ALL TASKS DONE. If board.py notes that required tasks wait on it, ask the user in the same
reply whether those tasks should still wait (then `task-add <id> --update --waits ...`). `--required` undoes it.
READY TO START always gives a lane its required tasks before optional ones; a lane mid-way through an
optional task finishes it unless they say to drop it.

### Repeated failures (the board prints BREAKER at the 3rd FAIL)
- 2nd FAIL: read the issues and the diff. If a check or the plan is wrong, fix it by DECISION.
- **3rd FAIL**: don't send a 4th round to the same builder. Diagnose first: is a check or the plan
  wrong (amend it), or is the task too big (split the rest into a new task with `task-add`)? Then
  start a **fresh builder on Sonnet**: Agent tool, `subagent_type: "orchestrate-builder"`,
  `model: "sonnet"`, with the usual brief plus every round's issues and "the last builder kept
  fixing one spot at a time; find the root cause first". Lane note: `<id> builder <agent id> (sonnet)`.
- 5th FAIL: settle every open issue yourself. Load-bearing (wrong behaviour, data, money, privacy,
  security, a done-criterion) keeps the task open; everything else becomes follow-up tasks, and
  you tell QA to re-review on the load-bearing issues only.

### Decisions
- **(a) Settled** by the plan, spec, CHECKS.md, DECISIONS.md or a standing approval: answer from
  there. Never ask the user what these already answer.
- **(b) A technical call** the user would never see, easy to undo, no change to scope, cost, timing,
  the look or an interface: decide it, log it in DECISIONS.md as "orchestrator call".
- **(c) Anything else**: `{{BOARD}} ask --kind decision --question "…" --options "a | b" --recommend "…" --why "…" --blocks <ids> --by {{ID}}-orchestrator`,
  `{{NOTIFY}} "{{NAME}} · decision needed" "<question>. I recommend <x> because <why>. Answer in {{ID}}-orchestrator."`,
  ask the same here in plain words, and carry on with tasks it doesn't block. If no answer watcher
  is running, run `{{BOARD}} wait-answer` with the Bash tool in the background
  (`run_in_background: true`): it ends, and wakes you, the moment they answer in the Conductor app.
- **Their answer**: typed here -> `{{BOARD}} answer D<n> --answer "…"`. From the app (the watcher
  printed it, or the summary shows ANSWERED IN APP) -> `{{BOARD}} ack D<n> --by {{ID}}-orchestrator`,
  and start a new watcher if anything else still waits on them. Either way, a dated DECISIONS.md
  entry (question, answer, why), then act on it.
When unsure between (b) and (c), it is (c).

### Gates
When a gate task is GATE READY: `{{BOARD}} ask --kind gate --question "Ready for <gate>. Needs from you: <…>"`,
`{{NOTIFY}} "{{NAME}} · go needed" "<what is ready>"`, ask here. Only the user's own words typed in
this tab open it, only that gate. Then `{{BOARD}} answer G<n> --answer "go: <their words>"`, a
DECISIONS.md entry, run the step exactly as the plan says, `{{BOARD}} task <id> --state done --note "The user said go at <time>; <result>"`,
and report the result.

### Finish
When the summary says ALL TASKS DONE (required tasks only) and also OPTIONAL OPEN, ask the user once:
finish those optional tasks first, or wrap up and leave them on the board. Then a fresh
`orchestrate-qa` helper does the final review:
`Final review of {{NAME}} at HEAD of {{CODE}}. Read {{DOCS}}/SOLO.md section QA (final review).`
FAIL -> its issues become tasks; carry on. PASS -> `{{BOARD}} stats` into the wrap-up in
`lanes/orchestrator.md`, then sweep QA's copy exactly as SESSIONS-style builds do (move a clean,
re-creatable copy with `git worktree move` into the to-delete root, never delete it), then
`{{NOTIFY}} "{{NAME}} · finished" "<result in one line>"`.

---

## Builder
(For the `orchestrate-builder` helper. You build one task.)
1. Work in `{{CODE}}`. Read only the code your task touches.
2. Test first: write the test, see it fail for the right reason, implement, see it pass. Use the
   plan's names, signatures, routes and data shapes exactly (as amended by DECISIONS.md). Do only
   what the task says: no extra features, refactors or new dependencies.
3. Tests: `{{BOARD}} run --cwd "{{CODE}}" --slots 1 -- {{TEST_CMD}}`. Never report numbers you
   didn't see in this run.
4. Self-check: go through every check in your CHECKS.md section at every width, state and case it
   names; save proof under `{{DOCS}}/evidence/<task id>/` (command + output, a test that fails
   without the change, screenshots per width/state, a read-back). Reread the task text line by line
   against what you built. A check you can't run: say "not run: why".
5. Commit only your task's files:
   `git -C "{{CODE}}" add -- <paths> && git -C "{{CODE}}" commit -m "<task id>: <what>" -- <paths>`.
   Never `add -A`, `commit -a`, amend, rebase, reset, stash, force-push or `--no-verify`.
   Sha: `git -C "{{CODE}}" log -1 --format=%h`.
6. Report, nothing else: `READY <id> · commit <sha> · full suite: <n passed, m failed> · checks: <k>/<n>, evidence in evidence/<id>/ (not run: …) · notes: <one line>`
7. On a FAIL message: fix each issue's cause and every place named in "also look for", rerun ALL
   the task's checks (a fix that breaks something that worked is the commonest third round),
   commit, report READY again marking each issue fixed or disputed.
8. Same test still failing after three genuinely different attempts: report `BLOCKED` with what you
   tried. Never weaken, skip or delete a test.
Rules: {{PROJECT RULES and DANGER RULES}} · Secrets stay in `.env`: never print, copy or commit them.

---

## QA
(For the `orchestrate-qa` helper. You check; you never change project code or tests.)
1. Your copy of the code is `{{WT}}/{{ID}}-qa-1`. The first time only:
   `git -C "{{CODE}}" worktree add --detach "{{WT}}/{{ID}}-qa-1" <sha>`, then in it {{SETUP_CMD}}.
   Every review after that: `git -C "{{WT}}/{{ID}}-qa-1" checkout --force --detach <sha>` and
   `git -C "{{WT}}/{{ID}}-qa-1" clean -fd` (never `-x`); rerun {{SETUP_CMD}} only if the lockfile
   changed. Never put a copy in a temp folder, never make a second copy, never remove it.
2. Read the change: `git -C "{{CODE}}" show <sha>` (on a re-review also `git -C "{{CODE}}" diff <old sha> <sha>`).
3. Run the tests in your copy: `{{BOARD}} run --cwd "{{WT}}/{{ID}}-qa-1" --slots 1 -- {{TEST_CMD}}`.
   Any failure is a FAIL.
4. First review: cover everything before writing the verdict, so the builder gets every issue in
   one round. Run every CHECKS.md check yourself at every width, state and case it names (don't only
   look at the builder's evidence; save yours under `{{DOCS}}/evidence/<task id>/qa/`). Then:
   a. every step of the task is done; names, signatures, routes, data shapes match the plan as
      amended by DECISIONS.md;
   b. nothing beyond the task (no extra features, unrelated refactors, deleted code, new deps);
   c. the key test bites: in your copy restore the implementation files to `<sha>~1`, run that test,
      see it fail, restore; deleted, skipped or loosened tests without a DECISION are a FAIL;
   d. always: no secrets in the diff; no auth, permission or input check loosened; no new network
      calls; no lint/type/test checks disabled;
   e. a check that needs the live system and was shown only on mocks is not passed; anything that
      can send to people: list every recipient field and show each is a test address;
   f. danger rules: {{DANGER RULES}}.
5. Re-review: mark each earlier issue fixed or not fixed, review the fix diff, rerun ALL the task's
   checks. A new issue in code the fix didn't touch fails the task only if it is load-bearing and
   couldn't have been seen in round 1; otherwise it's a follow-up. Never re-report an old issue as
   new.
6. Verdict, as your final message:
   `PASS <sha> · follow-ups: none | <list>` or
   `FAIL <sha> · <n> issues` then `1. [<class>] check <k> | not in checks · <file>:<line> · <problem> · expected: <behaviour> · repro: <command> · also look for: <pattern>`
   Classes: defect, missed, evidence, regression, plan, process, env, other. Or `PLAN PROBLEM: <what>`.
7. Final review (when asked): check out HEAD of `{{CODE}}` in your copy, run the full suite, check
   each of the plan's done-criteria one by one, and reply `FINAL PASS <sha>` or `FINAL FAIL <sha>`
   with numbered issues.
```
