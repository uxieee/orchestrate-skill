---
name: orchestrate
description: Turn a finished implementation plan into a multi-session Claude Code build - one orchestrator, one report-only QA, and one to four implementer lanes split by file ownership (or, for a one-lane plan, a single tab that runs builder and QA helpers) - with a project folder, rulebook, live board for the Conductor app, decision log, one-line launch commands, an orchestrator loop, and Telegram pings when you're needed. Use it whenever an implementation plan is done and the next step is running it, especially with several sessions or in parallel, and whenever the user says things like "set up the sessions", "make the orchestrator", "split this into lanes", "launch the build", "give me the prompts and the loop" or "orchestrate this", even if they don't name the skill.
---

# Orchestrate

You are turning a plan into a build that several Claude Code sessions run together. The user opens
the terminals and picks every session's model: never choose, suggest or comment on models. (The one
exception is the one-tab build's helpers, whose models the agent files fix: builders Haiku,
Sonnet after a third QA FAIL, QA Opus. The agent files set them; don't change them.) Your
output is files in the project plus one message telling them exactly what to run where.

The setup comes from real builds that worked:
files are the truth and messages are short typed nudges; one boss; QA that only reports and tests
the exact commit; lanes that never share files; gates that only the user opens.

## Scripts (use them; never hand-edit the files they own)

- `scripts/board.py` owns the board, `<docs>/state.json`, rendered to `STATUS.md`. It locks, so
  sessions can write at once; it refuses unsafe moves (done without a QA pass, a pass on the wrong
  commit, reopening done work); it shares test slots (`run`); it registers the project in
  `~/.conductor/projects.json`, which is how the Conductor app finds it. See `board.py --help`.
- `scripts/notify.sh "<title>" "<message>"` pings the user on Telegram plus a Mac notification. Exit 0
  Telegram sent, 3 Mac only, 1 nothing. Credentials are in `~/.conductor/telegram.env`; never read,
  print or copy that file's values.

Always call them with full quoted paths, one command per line (zsh doesn't split `$VAR` commands,
and paths often contain spaces):
`python3 "$HOME/.claude/skills/orchestrate/scripts/board.py" --docs "<abs docs>" <command> …`

## Workflow

### 1. Read the plan, collect the facts

From the plan (and spec) in this conversation or the files it names, collect:
- project name and a short kebab-case id (also the session prefix, e.g. `harbor`)
- the tasks: ids, titles, dependencies, and the files each touches
- the test command, the setup a fresh checkout needs (install deps, link `.env`), any deploy command
- the plan's review focus, anti-goals or danger rules, done-criteria, and project rules (copy
  rules, browsers, screen sizes)
- **gates**: steps that can't be undone or reach real people, real money or the public (deploy to
  live, write to a client's live CRM like GoHighLevel, send real email/SMS, push to main, delete real
  data, spend money)
- **standing approvals**: test and sandbox actions the build will repeat that are NOT gates because
  they are reversible and touch no real person (writes to a named sandbox location, TEST-prefixed
  objects, test emails to the user's own plus-addresses, preview deploys). In past builds about a fifth of
  everything put to the user was this kind of step, and they answered "you don't need me for this". Name
  each with its exact scope; anything outside that scope stays a gate.
- **shared resources** lanes would collide on (one logged-in browser profile, a staging site, a
  sandbox account): each gets a slot pool in SESSIONS.md (`board.py run --pool <name> --slots 1`)
- **acceptance checks per task**: what must be observably true for the task to count as done, and
  the evidence for each (a test that fails without the change, a command and its output, a
  screenshot at each named width and state, a read-back of the live object). Take them from the
  plan's task text, done-criteria and review focus. In past builds 60% of QA FAIL issues were a
  requirement or a piece of proof the implementer skipped, and QA found them one round at a time:
  writing the checks down first is the cheapest fix. Keep them few and concrete (3-8 per task).

If the plan has no task list, stop and say it needs one. If it doesn't say which files a task
touches, read the code it names and infer them. If it lacks a final full test run or
done-criteria, or a done-criterion no task delivers, say so and suggest adding a task; don't add
tasks silently.

Look for **interfaces between lanes the plan doesn't name** (the function one lane's screen exports
for another lane's router, who calls the mailer). Propose concrete names in the lane-split message;
once the user okays them, write them into DECISIONS.md so both lanes build against the same thing.

### 2. Decide the lanes, then check with the user

Lanes come from file ownership, because two sessions editing one file is how parallel builds break.
1. Group tasks whose files overlap into one lane; order each lane's tasks by dependency.
2. Find the files every task tends to touch (package manifests and lockfiles, routers or
   registries, shared types, migrations, test config, global CSS or tokens, `.gitignore`). Give
   each to exactly one lane; the others ask for changes. Owned paths must not nest across lanes:
   if a folder is shared, list files, not the folder.
3. Merge lanes that would sit idle most of the build or hold one or two small tasks. One to four
   implementer lanes; small or strictly sequential plans get one.
4. Name lanes by what they own (`backend`, `signing`, `frontend`, `data`), never `impl-1`.
Plus, always, one orchestrator and one QA.
5. **One lane means a one-tab build**: a single orchestrator tab that starts a builder helper per
   task (`orchestrate-builder`) and a separate QA helper to review it (`orchestrate-qa`), with the
   same CHECKS.md, board, QA on the exact commit, breaker and gates. It saves the user the extra tabs
   and their babysitting; with one lane there is no parallel work to lose. Use tabs only if they ask.
   Both agent files must exist in `~/.claude/agents/`; if not, say so and use tabs.

Steps only the user may run (launch, live writes) stay on the board as tasks on the lane
`orchestrator`, so progress can't reach 100% before them. The summary shows them as GATE READY.

Send the user one short chat message (no question popups): one-tab or multi-tab build, each lane with its tasks and what it owns,
one sentence on why this many lanes, the gates you found and "anything else that needs your go?",
the standing approvals you propose ("these run without asking you: ... ok?"), the tasks whose
done-criteria the plan leaves unclear (only those; don't list every check), any plan gaps and
proposed interface names. How they launch the sessions (models, permission mode,
flags) is their business: never ask about it or suggest it. **Wait for their ok or changes before step 3.**

### 3. Create the project folder

- **New project** (no code yet): the sessions open in `<workspace>/projects/<id>/`; the code lives
  there; docs = `<workspace>/projects/<id>/docs`. If there's no git repo, `git init` there.
- **Existing code elsewhere** (e.g. a `theme/` repo with deploy scripts): the sessions open in the
  workspace; docs = `<workspace>/projects/<id>/docs`; the code stays where it is. Never move
  existing code: it breaks remotes, deploy scripts and the plan's paths.

Then:
1. Put the plan and spec in the docs folder as `plan.md` and `spec.md`. If they're tracked in a git
   repo that the docs folder isn't in, copy them and leave a one-line pointer at the old path;
   inside the same repo, `git mv`. Fix links to them. Tell the user what moved.
2. Check the code repo's `.gitignore` covers dependency and build folders (`node_modules`, `.venv`,
   `dist`…): QA's copy is cleaned with `git clean -fd` before every review, which deletes anything
   untracked. If not, make it task 1's first step (tell the user in the lane-split message).
2b. If the docs folder is inside a git repo, add to its `.gitignore`: `state.json`, `STATUS.md`,
   `*.lock`, `.state.*.tmp`, `.STATUS.md.tmp`, `.tests.*.lock`, `.watchdog-pinged`.
3. If other `projects/*/docs/state.json` exist in this workspace, compare their lanes' `owns` with
   yours and warn the user about overlapping paths before going on.
4. Build the board, each a separate command (B = the full board.py call above):
   - `B init --id <id> --name "<Name>" --code "<abs code path>" --gates "<gate 1>; <gate 2>"`
   - `B lane <lane> --label "<Label>" --owns "<path>,<path>"` for each lane
   - `B session <id>-<lane> --role implementer --lane <lane> --no-seen` for each lane, then
     `B session <id>-qa --role qa --no-seen` and `B session <id>-orchestrator --role orchestrator --no-seen`
   - `B task-add <task> --title "<title>" --lane <lane> --waits "<ids>"` for each task, in plan order
   - `B validate`, and fix everything it reports.
5. Extra copies of the code live in one place. Create `<workspace>/.wt`. Only when it sits
   inside a repo, add `.wt/` to that repo's `.git/info/exclude` (`git -C "<repo>" rev-parse
   --git-path info/exclude` gives the file); otherwise nothing to add.
   `{{WT}}` in SESSIONS.md is `<workspace>/.wt`; fill `{{BUILD_DIRS}}` from the plan's build folders.
   Sessions keep one copy per role there (QA gets `<id>-qa-1`), never in a temp folder.
6. One-tab build: write `SOLO.md` from `references/solo-template.md` instead (fill every placeholder,
   `grep -n '{{' SOLO.md` must print nothing), register the same board sessions (the lane's session
   stands for the builder helper), and skip the rest of this item.
   Otherwise write `SESSIONS.md` from `references/sessions-template.md`: fill every placeholder, add each lane's
   brief (files to read closely, danger zone, stubs) and the project's danger rules to the QA
   checklist. `grep -n '{{' SESSIONS.md` must print nothing.
7. Write `DECISIONS.md` (a one-line header, plus any choices the planning conversation already
   settled and the standing approvals the user okayed, as dated entries) and `lanes/<lane>.md`,
   `lanes/qa.md`, `lanes/orchestrator.md` with "Not started."
7b. Write `CHECKS.md`: a one-line header, then for every task `## <task id> · <title>` and its
   numbered checks, each with its evidence (`1. <what is true> · evidence: <test name | command |
   screenshots at 1440/700/390, states x and y | read-back of …>`). Gate tasks get the check that
   proves the step worked live. `grep -c '^## ' CHECKS.md` must equal the number of tasks.
8. Add two lines to the CLAUDE.md in the folder the sessions open in (create it if missing; it is
   reloaded after compaction, the kickoff may not be): `If you are a <id>-* session: your role is
   in <docs>/SESSIONS.md (SOLO.md for a one-tab build). After any compaction, re-read it and DECISIONS.md and run the board summary.`

### 4. Pings and the watchdog

Run this exact command. It only counts lines and never shows a value, so it is safe:
`grep -c '^\(export \)\{0,1\}TELEGRAM_[A-Z_]*=.' ~/.conductor/telegram.env`. It should print 2.
If not, tell them the build works but pings will only reach the Mac.

Offer, in one line, a watchdog that pings them if the orchestrator's heartbeat goes silent for 45
minutes (its loop stops on usage limits, closed tabs and loop expiry). Only on a yes, install a
launchd agent running `board.py --docs "<docs>" watchdog` every 15 minutes
(`~/Library/LaunchAgents/com.conductor.<id>.watchdog.plist`, `StartInterval` 900, then
`launchctl load` it), and tell them how to remove it (`launchctl unload` + delete the file).

### 5. Hand over

One short message, in this order, and nothing about models, permission modes, flags or launch
commands (they handle those):
1. What you created (folder, files, lanes), three or four lines.
2. **The folder** to open every session in, as one absolute path.
3. **The sessions**, in start order: implementers and QA first, orchestrator last (it pings
   everyone). For each, its name and its prompt in one code block:
   - Orchestrator: `You are <id>-orchestrator, the orchestrator for <Name>. You run the build and write no code. Read <docs>/SESSIONS.md fully and follow its Orchestrator section, starting with Startup.`
   - QA: `You are <id>-qa, the QA reviewer for <Name>. You check and report; you never change code. Read <docs>/SESSIONS.md fully and follow its QA section.`
   - Implementer: `You are <id>-<lane>, the <lane> implementer for <Name>. Read <docs>/SESSIONS.md fully and follow its Implementer section, your row in the Lanes table and your lane brief.`
4. The gates, in one line.

The orchestrator starts its own `/loop`; the loop prompt lives in SESSIONS.md.

One-tab build: item 3 is a single session, `You are <id>-orchestrator, the orchestrator for <Name>. You run the build with builder and QA helpers and write no code. Read <docs>/SOLO.md fully and follow its Orchestrator section, starting with Startup.`
No loop: helpers report back on their own.

If you ever open the session windows yourself from your own shell (osascript, `open`), strip your
environment first: `for v in $(env | grep -o '^CLAUDE[A-Z_]*'); do unset "$v"; done;`. An app you
start inherits your `CLAUDE*` variables, and sessions started from it become your invisible
children, missing from ListAgents.

## Things to get right

- **Never pick models**, including for sub-agents (one-tab helpers excepted, see the top).
- **Token cost** comes mostly from long sessions re-reading context: short kickoffs, messages in the
  formats, the loop reads `board.py summary` not the plan, QA reads the commit not the tree,
  implementers read the plan's global sections plus their own tasks.
- **Files beat messages.** Anything a session must remember after compaction goes in a file.
- **QA never fixes.** Its value is an independent check of the exact commit. QA has not been the
  problem in past builds (no FAIL was over-strict); rework comes from tasks handed in incomplete, so
  the fixes live upstream: checks written first, the implementer's self-check, one complete first
  review, and a breaker at the third FAIL instead of more of the same rounds.
- **Measure.** `board.py stats` gives first-pass QA yield, fails per task, fail classes and waiting
  items for one build (`--all` for every registered build); the orchestrator records it at Finish,
  so changes to this skill can be judged on numbers, not impressions.
- **Only the user opens gates**, by typing "go" in the orchestrator, which then runs the step itself.
- Plain language in everything the user reads: short sentences, outcome first.
