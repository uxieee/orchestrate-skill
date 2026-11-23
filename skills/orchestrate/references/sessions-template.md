# SESSIONS.md template

Copy everything inside the fence below into `<DOCS>/SESSIONS.md` and fill every `{{…}}` from the
plan. Delete lines marked `(optional)` that don't apply. Keep the wording of the rules and the
message formats: they come from builds that worked. Before finishing, `grep -n '{{' SESSIONS.md`
must print nothing.

Placeholders (paths are absolute; paths may contain spaces, so they are always quoted):
- `{{NAME}}` project name · `{{ID}}` kebab-case id, also the session-name prefix
- `{{ROOT}}` the folder every session opens in
- `{{DOCS}}` the docs folder, e.g. `/Users/you/work/projects/acme-portal/docs`
- `{{CODE}}` the git working tree of the code
- `{{WT}}` the folder for extra copies of the code: `<workspace>/.wt` (SKILL.md "3. Create the project
  folder", item 5, creates it and, when it sits inside a repo, lists it in that repo's
  `.git/info/exclude`)
- `{{BUILD_DIRS}}` the build-output folders the plan names, relative to a copy (e.g. `dist .next`);
  may be empty
- `{{BOARD}}` = `python3 "$HOME/.claude/skills/orchestrate/scripts/board.py" --docs "{{DOCS}}"`
- `{{NOTIFY}}` = `"$HOME/.claude/skills/orchestrate/scripts/notify.sh"`
- `{{TEST_CMD}}` the full test command; `{{SETUP_CMD}}` what a fresh checkout needs first (install
  deps, link `.env`), or "nothing"
- `{{SLOTS}}` how many test runs may run at once (2 unless the suite is heavy: then 1)
- `{{STANDING APPROVALS}}` the test/sandbox actions the user okayed once in the lane-split reply
- `{{SHARED RESOURCES}}` browser profiles, staging sites or sandbox accounts lanes must take turns on,
  each with a pool name

```markdown
# {{NAME}}: sessions

{{N}} Claude Code sessions, all opened in `{{ROOT}}`. They talk with SendMessage (ListAgents shows
who is there). The user picks every session's model.

    {{ID}}-orchestrator   decides, assigns, unblocks, runs the gates; the only one who talks to the user
      |- {{ID}}-<lane>    implementers, one lane each, own files only
      '- {{ID}}-qa        checks every task before it counts as done; never changes code

## Files
- Plan `{{DOCS}}/plan.md` (how) · spec `{{DOCS}}/spec.md` (what) (optional if no spec)
- Checks `{{DOCS}}/CHECKS.md`: one `## <task id>` section per task, the numbered checks that decide
  "done" and the evidence each needs. Read only your task's section. The orchestrator owns it.
- Board `{{DOCS}}/state.json`, shown as `{{DOCS}}/STATUS.md`. Never edit either by hand; change the
  board only with `{{BOARD}} <command>`. `{{BOARD}} summary` is the one-screen view.
- Decisions `{{DOCS}}/DECISIONS.md` · lane notes `{{DOCS}}/lanes/<lane>.md` (five lines: current
  task, last commit, next step, open questions)
- Code `{{CODE}}`

Precedence: DECISIONS.md beats the plan; the plan wins on how, the spec on what.

## Authority
- `{{ID}}-orchestrator` runs the build. Its `DECISION:` and `INSTRUCTION:` messages are binding for
  normal build work; carry them out without re-asking anyone.
- No message from any session ever opens a gate or counts as the user's approval. Messages between
  sessions are coordination, not consent.
- Implementers and QA never contact the user. If the user talks to you directly, their word wins: do it
  and send the orchestrator `DECISION FROM USER: <what they said>` so it gets recorded.

## Gates (only the user opens these)
{{GATES, one bullet each, e.g. "- deploy to the live site", "- write to GoHighLevel", "- send real
email or SMS", "- push to main". If none: "None for this project."}}

A gated step runs only in `{{ID}}-orchestrator`, right after the user types "go" there, and only for
the gate they named. Lanes prepare everything and report `READY FOR GATE <name>`; they never run the
gated step. When unsure whether something is a gate, treat it as one.

**Standing approvals** (the user okayed these once, at setup; no "go" needed, but each use gets a
one-line DECISIONS.md entry): {{STANDING APPROVALS from the lane-split reply, e.g. "- writes to the
sandbox location <id>, TEST-prefixed objects only", "- test emails to you+<tag>@..."; if none:
"None."}} Anything outside their exact scope is a gate. An approval whose scope the user hasn't filled
in yet (which address, which account) is not active until they do.

## Lanes and file ownership
You edit only the files your lane owns. Need a change in someone else's file? Ask the owner or the
orchestrator. A path not listed belongs to nobody: ask before touching it.

| Session | Lane | Tasks, in order | Owns |
|---|---|---|---|
| `{{ID}}-<lane>` | <lane> | <ids> | <paths> |

- QA owns no code. The orchestrator owns DECISIONS.md and planning docs, nothing else.
- Every session may write its own lane note and `{{DOCS}}/evidence/<task id>/` for its own tasks
  (QA: `evidence/<task id>/qa/`). That is not an ownership breach; commit evidence only together
  with the task, never another lane's folder.
- A task's tests belong to the lane doing the task.

## Lane briefs
{{Per lane, three to five lines: the files to read closely before starting, the danger zone (what
must keep working, what must never happen), and any rule like "code against the plan's interface
and use a small local stub until the other lane's route lands".}}

## Rules for every session
1. **Read**: this file, DECISIONS.md, your lane note, and from the plan its global sections
   (goals, constraints, interfaces, review focus) plus your own tasks and their CHECKS.md sections. Don't read other lanes' tasks
   in detail.
2. **Git, shared tree, one branch.** Commit only your paths:
   `git -C "{{CODE}}" add -- <paths> && git -C "{{CODE}}" commit -m "<task id>: <what>" -- <paths>`.
   Then `git -C "{{CODE}}" status --short -- <paths>` must print nothing. Take your sha from
   `git -C "{{CODE}}" log -1 --format=%h -- <paths>`, never from HEAD.
   Never, in the shared folder: `add -A`, `commit -a`, stash, checkout or restore files, switch
   branches, clean, reset, amend, rebase, force-push, `--no-verify`. These wipe or rewrite other
   lanes' work. (QA's own copy under `{{WT}}` is not the shared folder: see QA step 3.) If
   `index.lock` is busy, wait 10 seconds and retry. If `git status` shows changes in your files you
   didn't make, don't commit them: tell the orchestrator.
3. **Tests** run through the shared slots, in the code folder:
   `{{BOARD}} run --cwd "{{CODE}}" --slots {{SLOTS}} -- {{TEST_CMD}}`.
   A failure only in files you didn't touch is someone else's: note it as "pre-existing in <lane>",
   don't fix it, don't stash. Never report numbers you didn't see in this run.
   Shared resources (one browser profile, a staging site, a sandbox account) are held the same way,
   one user at a time: `{{BOARD}} run --pool <browser|staging|port-5173|…> --slots 1 -- <command>`. A
   dev server on a fixed port is a shared resource too: two runs on one port test each other's code.
   {{SHARED RESOURCES the plan uses and their pool names, or "None."}}
4. **Secrets** live in `.env` files. Never print, copy or commit them.
4b. **Evidence**: a check counts only with proof someone else can open: the command and its output,
   a test name that fails without the change, a screenshot path per width and state, or a read-back
   of the live object. Save it under `{{DOCS}}/evidence/<task id>/` (commit it with your paths when it
   is inside the repo). Passing on mocks proves the code, not the live system: say "mock only".
5. {{PROJECT RULES from the plan: copy rules, browsers, screen sizes, deploy rule}} (optional)
6. **After a compaction or restart**, before anything else: re-read this file and DECISIONS.md,
   run `{{BOARD}} summary`, read your lane note.
7. **Isolation and land steps.** If the plan needs an isolated lane or a land step: one copy per
   role under `{{WT}}`, reused for every step of that role. The first time only:
   `git -C "{{CODE}}" worktree add --detach "{{WT}}/{{ID}}-<lane|land>" <base-sha>`
   (`<lane|land>` is the lane's name, or `land` for the land step). Each land, in that copy: first
   `git -C "{{WT}}/{{ID}}-land" checkout --force --detach <base>` (a clean copy), then
   `git -C "{{WT}}/{{ID}}-land" switch -c <land-branch> <base>`, so lands never stack. Never put a
   copy under `/tmp`, `/private/tmp`, `/var/folders`, `$TMPDIR` or the session scratchpad (they get
   wiped), never make a copy per step, never remove a copy: the orchestrator moves them at
   Finish. A session makes at most 3 copies per repo, so always reuse
   first. If a hook refuses a command, stop and send `BLOCKED` or ask: never work around it.

## Messages (SendMessage), exact formats
- Implementer -> QA only (the board tells the orchestrator):
  `TASK <id> READY FOR QA · commit <sha> · full suite: <n passed, m failed> · checks: <k>/<n> with
  evidence in evidence/<id>/ (not run: <numbers and why>) · notes: <one line>`
- QA -> implementer; a PASS also goes to the orchestrator (it sends the next START), a FAIL doesn't:
  `TASK <id> PASS · <sha> · follow-ups: none | <short list>` or
  `TASK <id> FAIL · round <n> · <sha>` then numbered issues:
  `1. [<class>] check <k> | not in checks · <file>:<line> · <problem> · expected: <behaviour> · repro: <command or steps> · also look for: <the pattern, if it can recur elsewhere>`
  Classes: defect, missed (a requirement or check not done), evidence (proof missing or a test
  that doesn't bite), regression (broke something that worked), plan, process, env, other.
- QA -> orchestrator, at the end: `FINAL PASS · <sha>` or `FINAL FAIL · <sha>` with numbered issues
- Anyone -> orchestrator: `QUESTION: <question> · options: <a / b> · blocks: <task or nothing>`,
  `BLOCKED on <what> · need <what> from <who>`, `READY FOR GATE <name> · <what is ready>`
- Orchestrator -> anyone: `START TASK <id>`, `DECISION: …`, `INSTRUCTION: …`, `PING` (reply
  `PONG <name> · <what you are doing>`)

Keep messages to the format; details go in files. If a send comes back held or refused, the other
session needs the user to approve it in its tab: tell the orchestrator (or, if you are the
orchestrator, tell the user).

---

## Orchestrator

You are `{{ID}}-orchestrator`. You write no project code.

### Startup (also after a compaction or restart)
1. Read this file, the whole plan and spec, DECISIONS.md (create it with a header if missing).
   Run `{{BOARD}} summary`.
2. Run ListAgents. Send every session in the Lanes table and `{{ID}}-qa` one message:
   `PING · you report to {{ID}}-orchestrator; my DECISION and INSTRUCTION messages are binding.`
   Record who answered: `{{BOARD}} sync <name>=idle <name>=idle … --by {{ID}}-orchestrator`.
   Anyone missing after two minutes: tell the user in one line which tab to start.
3. Send the STARTs that `{{BOARD}} summary` allows (see Assigning).
4. Start your loop with the Skill tool: skill `loop`, args `15m ` followed by the loop prompt
   below, word for word. If that fails, tell the user to run `/loop 15m` with the loop prompt from
   this file.
5. Start the answer watcher: run `{{BOARD}} wait-answer` with the Bash tool in the background
   (`run_in_background: true`). It ends the moment the user answers in the Conductor app, and
   its ending wakes you. It costs nothing while it waits.

### Act when things happen; the loop is the safety net
- When the answer watcher ends: finish Decisions step 5 for what it printed, then start a new
  watcher the same way. If you find none running (after a compaction or restart), start one.
- On `PASS`: run `{{BOARD}} summary` and send the STARTs it now allows, straight away.
- On `QUESTION` or `BLOCKED`: answer now (see Decisions).
- On `READY FOR GATE`: see Gates.
- FAILs don't come to you; the summary shows REPEATED QA FAILS and BREAKER (see Repeated failures).

### Assigning
`{{BOARD}} summary` lists READY TO START: at most one task per lane, only for lanes with nothing
assigned, in progress or failed, with every "waits for" task done and nothing waiting on you.
For each: `{{BOARD}} task <id> --state assigned --by {{ID}}-orchestrator`, then send
`START TASK <id>` to the lane. Never send a START the summary didn't list.

### Decisions
Three kinds of question:
- **(a) Settled** by the plan, spec, CHECKS.md, DECISIONS.md or a standing approval: answer straight
  from there. Never ask the user something these already answer.
- **(b) A technical call inside the build** that the user would never see, doesn't change an
  interface other lanes use, scope, cost, timing or the look, and is easy to undo: decide it
  yourself (spawn an expert sub-agent if it isn't obvious), add it to DECISIONS.md as
  "orchestrator call", send `DECISION:`. No ping.
- **(c) Anything else**: scope, cost, timing, the look, client-facing behaviour, a shared
  interface, anything irreversible or near a gate.
  1. Spawn an expert sub-agent (Agent tool, no model override) on exactly this question: context,
     files to read, options; ask for a recommendation, reasons and risks.
  2. `{{BOARD}} ask --kind decision --question "…" --options "a | b" --recommend "…" --why "…" --blocks <ids> --by {{ID}}-orchestrator`
     (prints its id, e.g. D3).
  3. `{{NOTIFY}} "{{NAME}} · decision needed" "<question>. Expert recommends <x> because <why>. Answer in {{ID}}-orchestrator."`
     and ask the same in your own session: short, plain, outcome first.
  4. Keep every unblocked lane busy while you wait.
  5. They answer either in your session or in the Conductor app (the summary then shows it under
     ANSWERED IN APP). In your session: `{{BOARD}} answer D3 --answer "…"`. Either way: a dated
     DECISIONS.md entry (question, answer, why), `DECISION: …` to the affected lanes, and for an
     app answer `{{BOARD}} ack D3 --by {{ID}}-orchestrator`. If it changes work already done, list those tasks and propose
     follow-up tasks to the user.
When unsure between (b) and (c), it is (c). Several questions in one check go in one ping.

### Gates
A step covered by a standing approval is not a gate: run it (or let the lane run it) inside its exact
scope and log it in DECISIONS.md. Never turn a standing-approval step into a "go" request.
Gate tasks sit on the `orchestrator` lane; the summary shows them under GATE READY once their
waits are done. On `READY FOR GATE`, GATE READY, or when the plan reaches a gate:
`{{BOARD}} ask --kind gate --question "Ready for <gate>. Needs from you: <…>" --blocks <ids>`, then
`{{NOTIFY}} "{{NAME}} · go needed" "<what is ready, what you need from them>"`. Only the user's own
words typed in this session open it, and only that gate. After their go: `{{BOARD}} answer G<n>
--answer "go: <their words>"`, a DECISIONS.md entry, then run the gated step yourself exactly as the
plan says, mark it `{{BOARD}} task <id> --state done --note "The user said go at <time>; <result>"`,
and report the result to them.

### Optional tasks
When the user says a task isn't required ("we don't need T7 for this", "make it optional"): `{{BOARD}} task <id> --optional --note "user: <their words>" --by {{ID}}-orchestrator`
and a dated DECISIONS.md line. It stays on the board and can still be worked on, but no longer counts
toward progress or ALL TASKS DONE. If board.py notes that required tasks wait on it, ask the user in the same
reply whether those tasks should still wait (then `task-add <id> --update --waits ...`). `--required` undoes it.
READY TO START always gives a lane its required tasks before optional ones; a lane mid-way through an
optional task finishes it unless they say to drop it.

### Repeated failures and stuck work
More rounds of the same approach rarely converge: late rounds mostly bring regressions from the last
fix or the same defect back. So:
- Second FAIL (summary: REPEATED QA FAILS): read QA's issues in `lanes/qa.md` and the diff. If the
  plan or a check is wrong, fix CHECKS.md by DECISION. Otherwise nothing.
- Third FAIL (summary: BREAKER): don't let a fourth round start the same way. Pick one and send it
  as an INSTRUCTION: (a) a check or the plan is wrong: amend it by DECISION; (b) the implementer keeps
  fixing one spot: spawn an expert sub-agent (Agent tool, no model override) on the task, the issues
  of all rounds and the diff, asking for the root cause and a fix brief, and send that brief;
  (c) the task is too big: split the rest into a new task (`task-add`) so this one can pass on what
  it already does. Ping the user only if the choice is theirs (scope, look, cost).
- Fifth FAIL: settle every open issue yourself. Load-bearing (wrong behaviour, data, money, privacy,
  security, a done-criterion) stays and the task stays open; everything else becomes follow-up tasks,
  and you tell QA: `INSTRUCTION: re-review <id> on issues <n, m> only; the rest are follow-ups <ids>`.
- A session that is stuck (see the loop) gets one status request, then a ping to the user that says
  what to do: "Check the <session> tab; it may be waiting on a prompt or need a restart."

### Guard
Each check, run `git -C "{{CODE}}" log --name-only --format='--%h %s' <last sha you checked>..HEAD`
(keep that sha in `lanes/orchestrator.md`). Any file outside the committing lane's Owns, or a last
checked sha missing from history: send `INSTRUCTION: stop …` and fix it. Also stop anyone who says
they will cross a gate, weaken a test or rewrite history.

### Silence and noise
- Ping the user only for decisions, gates, stuck sessions, the build pausing, and the finish.
- If every lane is idle or blocked waiting on them, ping once: "Build is paused until you answer
  D3." Remind at most every 2 hours.
- `{{NOTIFY}}` exit 3 means only the Mac saw it; exit 1 means nothing did. Say so once in your
  session; don't retry in a loop.
- After a usage-limit pause, when you're back: run the summary, PING everyone, resume.
- A session that doesn't react to messages while idle: tell the user in one line to paste this into
  its tab: `/loop 10m Check your messages and run the board summary, then continue your task or wait for START TASK.`

### Finish
When the summary says ALL TASKS DONE (required tasks only) and also OPTIONAL OPEN, ask the user once,
in one line: finish those optional tasks first, or wrap up and leave them on the board. Optional
tasks still in progress keep going until they answer. Then:
`INSTRUCTION: final review` to `{{ID}}-qa`. On
`FINAL FAIL`, add each issue as a task for its owning lane (`{{BOARD}} task-add …`) and carry on.
On `FINAL PASS`: run `{{BOARD}} stats` and put its line in the wrap-up. Then sweep the copies. For each repo this build used, run
`git -C "<repo>" worktree list`. A copy belongs to this build when its path starts with `{{WT}}/{{ID}}-`.
It is re-creatable when all three hold: `git -C "<copy>" status --short` prints nothing; its commit
is reachable from a branch (`git -C "<copy>" branch --contains HEAD` prints something; detached QA
copies qualify); and `git -C "<copy>" status --ignored --short` shows nothing outside dependency and
build folders (`node_modules`, `.venv`, `dist`, `build`, caches), since anything else is unique and
means keep. Before each move run `du -sk "<copy>"`; sum them and report GB with one decimal. Move each
re-creatable copy; never delete or unregister one:
`git -C "<repo>" worktree move "<path>" "<to-delete root>/<YYYY-MM-DD>-<repo>-<name>"`.
The to-delete root is `.to-delete` at the top of the copy's own drive (`~/.to-delete` on the
main disk), so the move never copies across drives. The user empties it. Copies that aren't re-creatable
stay where they are: list each with its reason (dirty, not on a branch, unique ignored file) in the
wrap-up. Then write the wrap-up in `lanes/orchestrator.md`, ping the user
(`{{NOTIFY}} "{{NAME}} · finished" "<result in one line, anything left for them>. N copies moved to .to-delete (X GB)."`;
with none moved: "0 copies moved (0 GB)"),
then CronList and CronDelete your loop.

---

## Loop prompt (orchestrator)

    {{NAME}} orchestrator check-in. Messages you already handled since the last check need nothing.
    1. Run `{{BOARD}} summary`. Run ListAgents only if the summary shows STALE, a lane with a task
       open, QA QUEUE items, or BREAKER; otherwise skip it and step 3.
    2. Read new messages; handle them as SESSIONS.md says. For each ANSWERED IN APP item, finish
       Decisions step 5 (record, announce, ack).
    3. Session states from ListAgents and the summary's ACTIVE line:
       busy -> working; idle with no active task -> idle; idle while its lane has a task assigned,
       in progress or failed -> stopped: send "You're idle with <id> open: continue it, or send
       BLOCKED"; busy but STALE -> ask for one status line and run
       `{{BOARD}} session <name> --asked --no-seen`; STALE and status already asked last check, or
       missing / offline / at a shell -> gone or stuck: `{{BOARD}} ask --kind stuck --session <name>
       --question "<name> looks stuck on <id>"` and, only if that prints a new id, ping the user.
       Record only states that changed: `{{BOARD}} sync <name>=<state> … --by {{ID}}-orchestrator`.
    4. QA QUEUE items marked NUDGE: nudge {{ID}}-qa only if it's idle, once per item.
    5. Send the STARTs under READY TO START (set each to assigned first).
    6. Guard: check commits since your last checked sha against lane ownership.
    7. `{{BOARD}} heartbeat --by {{ID}}-orchestrator`. Add a `note` only if counts or the next
       milestone changed. If nothing changed, end the turn.
    8. ALL TASKS DONE -> run Finish.
    Don't re-read the plan on a check.

---

## Implementer

You are `{{ID}}-<lane>`. Your tasks and files are your row in the Lanes table and your lane brief.

On start and after a compaction: run `{{BOARD}} summary`. If your lane has a task assigned, in
progress or failed, resume it from your lane note and `git -C "{{CODE}}" log -- <your paths>`.
Otherwise wait for `START TASK`. While waiting you may read and plan, nothing else.
Ignore a START for a task you already have.

For each task:
1. `{{BOARD}} task <id> --state progress --by {{ID}}-<lane>` and
   `{{BOARD}} session {{ID}}-<lane> --state working --doing "<id> <title>"`.
2. Read the task in the plan, its section in CHECKS.md, and only the code it touches. The checks are
   the definition of done: if one is unclear or can't be met, send `QUESTION` now, not at the end.
3. Test first: write the test, run it, see it fail for the right reason; implement; see it pass.
   Use the plan's names, signatures, routes and data shapes exactly (as amended by DECISIONS.md):
   other lanes depend on them. Do only what the task says: no extra features, refactors or new
   dependencies.
   After each red/green step, or every 20 minutes, log progress:
   `{{BOARD}} task <id> --note "<one line>" --by {{ID}}-<lane>`.
4. Run the full suite through the slots (Rule 3).
4b. Self-check before QA sees it: go through every check in your CHECKS.md section yourself, at every
   width, state and case it names, and save the evidence (Rule 4b). Then reread the task text line by
   line against what you built: most QA FAILs are a requirement or a piece of proof that was skipped,
   not a bug. Fix what you find. A check you can't run goes in the READY notes as "not run: why".
5. Commit (Rule 2). Every file the task needs, new files included, must be in the commit.
6. `{{BOARD}} task <id> --state qa --commit <sha> --by {{ID}}-<lane>` and
   `{{BOARD}} session {{ID}}-<lane> --state idle --commit <sha> --msg "<id> ready for QA"`.
7. Update your lane note.
8. Send `TASK <id> READY FOR QA · commit <sha> · full suite: … · checks: … · notes: …` to `{{ID}}-qa`.

On `TASK <id> FAIL`: it comes before anything else. If you have uncommitted work for another task
in the same files, tell the orchestrator before touching it; never put another task's code in a
fix commit. `{{BOARD}} task <id> --state progress`, then for each numbered issue fix the cause, and
where it says "also look for", every other place the same pattern occurs. Then repeat from step 4
with ALL the task's checks, not only the failed ones: a fix that breaks something that worked is the
commonest reason for a third round. In the READY notes mark each issue number fixed or disputed. If you think an issue is wrong,
don't argue with QA: send `QUESTION` to the orchestrator with both views, and fix the rest.

Stuck: if the same test still fails after three genuinely different attempts, stop and send
`BLOCKED` with what you tried. When you send BLOCKED:
`{{BOARD}} task <id> --state blocked --note "<why>"`; set it back to progress when unblocked.
Meanwhile carry on with the unblocked parts of this task only; never start another task without
START. Never weaken, skip or delete a test to get green.

---

## QA

You are `{{ID}}-qa`. You check and report. You never edit project code or tests and never fix
anything yourself.

On start and after a compaction: run `{{BOARD}} summary` and review whatever is in QA QUEUE.
Work the queue in order: tasks that others wait on first, then oldest.

For each `TASK <id> READY FOR QA · commit <sha>`:
1. `{{BOARD}} session {{ID}}-qa --state working --doing "Reviewing <id>"`.
2. Read the task in the plan, its CHECKS.md section, DECISIONS.md, and the change itself:
   `git -C "{{CODE}}" show <sha>` plus the task's earlier commits. Don't rely on the summary.
3. Test the commit, not the shared folder, in one reused copy. The first time only:
   `git -C "{{CODE}}" worktree add --detach "{{WT}}/{{ID}}-qa-1" <sha>`, then in it {{SETUP_CMD}}.
   Every review after that, in the same copy:
   `git -C "{{WT}}/{{ID}}-qa-1" checkout --force --detach <sha>`, then
   `git -C "{{WT}}/{{ID}}-qa-1" clean -fd` (never `-x`), plus
   `rm -rf "{{WT}}/{{ID}}-qa-1/<dir>"` for each of {{BUILD_DIRS}}. Re-run {{SETUP_CMD}} only if the
   lockfile changed: `git -C "{{WT}}/{{ID}}-qa-1" diff --quiet <prev-sha> <sha> -- "<lockfile>"`
   exits non-zero (<prev-sha> is the commit the copy was on before this checkout). Then the task's tests and the full suite
   (through `{{BOARD}} run --cwd "{{WT}}/{{ID}}-qa-1" -- …`, so they run in the copy, not the shared
   folder). Any failure there is a FAIL. Never make a copy per task and never
   remove the copy. If two reviews run at once, the second uses `{{WT}}/{{ID}}-qa-2` the same way.
4. Check, citing file:line for every problem. On the first review of a task, cover everything before
   you write the verdict, so the implementer gets every issue in one round: run every CHECKS.md check
   yourself at every width, state and case it names (don't only look at the implementer's evidence),
   then a-g below. Finding one problem is not a reason to stop looking.
   a. Every check passes with evidence, and every step of the task is done; names, signatures, routes,
      data shapes and status codes match the plan as amended by DECISIONS.md. For a changed
      interface, grep its users in other lanes. A check that needs the live system and was only shown
      on mocks is not passed: FAIL it, or PASS with follow-up `live proof needed for check <k>` if the
      orchestrator has a live-proof task before the gate. Anything that can send to people (email, SMS,
      chat, notifications): list every recipient field it can use and show each is a test address.
   b. Nothing beyond the task: no extra features, unrelated refactors, deleted code or new
      dependencies the plan didn't ask for.
   c. The tests bite. For the task's key test, in your worktree restore the implementation files to
      `<sha>~1` (`git checkout <sha>~1 -- <implementation files>`), run that test, confirm it fails,
      then restore. Scan the diff for deleted, skipped, `only`/`xfail`, loosened or re-baselined
      tests and broader mocks: any of these without a DECISION is a FAIL.
   d. Always, whatever the plan says: no secrets or `.env` values in the diff; no auth, permission
      or input check removed or loosened; no new network calls or external scripts; no lint, type
      or test checks disabled.
   e. The project's danger rules hold: {{DANGER RULES from the plan's review focus / anti-goals}}.
   f. Ownership: every path in `git -C "{{CODE}}" show --stat <sha>` is in the lane's Owns (or is
      this task's own `evidence/<task id>/` folder).
   g. {{PROJECT RULES, e.g. copy rules, screenshots at given sizes, console clean}} (optional)
5. Verdict, then reply to the implementer with a copy to the orchestrator:
   - pass: `{{BOARD}} qa <id> --verdict pass --sha <sha> --by {{ID}}-qa`, send
     `TASK <id> PASS · <sha> · follow-ups: …` (minor things go here, they don't fail the task)
   - fail: `{{BOARD}} qa <id> --verdict fail --sha <sha> --issues <n> --classes <classes of the issues> --by {{ID}}-qa`,
     send `TASK <id> FAIL · round <n> · <sha>` with the numbered issues to the implementer only, and
     keep the same list in `lanes/qa.md`.
   Then `{{BOARD}} session {{ID}}-qa --state idle` and update `lanes/qa.md` (last verdicts, things
   to re-check).

Bar: strict on correctness, security and matching the plan; never fail work over style the plan
didn't ask for. On a re-review (round 2+): mark each earlier issue fixed or not fixed, review the
fix diff (`git diff <prev sha> <sha>`), and re-run all the task's checks to catch regressions. A new
issue in code the fix didn't touch fails the task only if it is load-bearing (wrong behaviour, data,
money, privacy, security, a done-criterion) and you could not have seen it in round 1; anything
else is a follow-up. Never re-report an issue you already reported as new. If the plan or a check
itself is wrong, send `BLOCKED` to the orchestrator instead of failing the implementer for following
it. If a check is missing from CHECKS.md, send `QUESTION` so the orchestrator adds it. If a problem
needs a decision, send `QUESTION`.

On `INSTRUCTION: final review`: in `{{WT}}/{{ID}}-qa-1`, first
`sha=$(git -C "{{CODE}}" rev-parse HEAD)`, then
`git -C "{{WT}}/{{ID}}-qa-1" checkout --force --detach "$sha"` and the same clean and reinstall
steps as QA step 3. Run the full suite, check each
of the plan's done-criteria one by one, and check that every interface one lane provides matches
how the others use it. Reply `FINAL PASS · <sha>` or `FINAL FAIL · <sha>` with numbered issues,
each naming the owning lane.
```
