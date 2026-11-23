/* Conductor mockup data. FAKE: invented projects, people and numbers.
   Every concept renders from this file so the five can be compared like for like.
   Loaded with <script src="../data.js"> and read from window.CONDUCTOR. No modules, works from file://. */
(function () {
  // "Now" for every relative time on screen: Thursday 29 Oct 2026, 14:32. All ages below are minutes before now.
  var NOW = { iso: "2026-10-29T14:32:00", label: "Thu 29 Oct, 14:32" };

  // Task states, in board order. `waits` lists the task ids that must be done first.
  var STATES = [
    { id: "todo",     label: "To do" },
    { id: "progress", label: "In progress" },
    { id: "qa",       label: "Ready for QA" },
    { id: "fail",     label: "QA failed" },
    { id: "blocked",  label: "Blocked" },
    { id: "done",     label: "Done" }
  ];

  // t(id, title, lane, state, waits, commit, minutesSinceLastChange)
  function t(id, title, lane, state, waits, sha, age) {
    return { id: id, title: title, lane: lane, state: state, waits: waits ? waits.split(",") : [], commit: sha, age: age };
  }

  var projects = [
    {
      id: "harbor", name: "Harbor Portal", client: "Harbor Clinics",
      phase: "Round 3 of 8", started: "20 Oct", target: "Fri 6 Nov",
      finding: "A18 failed QA 95 min ago and it holds up the launch checklist.",
      lanes: [
        { id: "backend",  label: "Backend",  hue: 28  },
        { id: "signing",  label: "Signing",  hue: 205 },
        { id: "frontend", label: "Frontend", hue: 150 }
      ],
      sessions: [
        { name: "harbor-orchestrator", role: "orchestrator", state: "working", seen: 1,  task: "Checking the board after A17 went to QA", model: "Opus" },
        { name: "harbor-qa",           role: "qa",           state: "working", seen: 2,  task: "A17 clinic dashboard, running the suite", model: "Opus" },
        { name: "harbor-backend",      role: "backend",      state: "working", seen: 1,  task: "A16 GHL notes and field writes", model: "Sonnet" },
        { name: "harbor-signing",      role: "signing",      state: "quiet",   seen: 41, task: "A20 reminder emails, no commit for 41 min", model: "Sonnet" },
        { name: "harbor-frontend",     role: "frontend",     state: "working", seen: 1,  task: "A19 staff order queue UI", model: "Sonnet" }
      ],
      tasks: [
        t("A1",  "Sign-in and password reset",   "backend",  "done",     "",        "f7547ba", 2880),
        t("A2",  "Invite acceptance",            "backend",  "done",     "A1",      "a1c93d2", 2700),
        t("A3",  "Clinic account model",         "backend",  "done",     "",        "d30626f", 2600),
        t("A4",  "Staff order status flow",      "backend",  "done",     "A3",      "9be41a0", 2300),
        t("A5",  "Shipped email",                "backend",  "done",     "A4",      "3c7e2f8", 2100),
        t("A6",  "Terms page and acceptance",    "signing",  "done",     "A2",      "e5a0b17", 2400),
        t("A7",  "Two-step paperwork setup",     "signing",  "done",     "A6",      "71d9c04", 1900),
        t("A8",  "Document list and downloads",  "signing",  "done",     "A7",      "b8f26e3", 1700),
        t("A9",  "Signed PDF archive",           "signing",  "done",     "A8",      "04a7d5c", 1500),
        t("A10", "Portal shell and navigation",  "frontend", "done",     "",        "62f8e19", 2500),
        t("A11", "Catalog grid",                 "frontend", "done",     "A10",     "c4d1a85", 2200),
        t("A12", "Product detail page",          "frontend", "done",     "A11",     "8a3e6f0", 2000),
        t("A13", "Cart and order summary",       "frontend", "done",     "A12",     "1f9b7d2", 1800),
        t("A14", "Payments page",                "frontend", "done",     "A13",     "e0c58a4", 1400),
        t("A15", "Order history",                "backend",  "qa",       "A4",      "5d2a9c1", 25),
        t("A16", "GHL notes and field writes",   "backend",  "progress", "A5",      "",        12),
        t("A17", "Clinic dashboard",             "frontend", "qa",       "A14",     "7e1b4f6", 40),
        t("A18", "Payment receipts",             "backend",  "fail",     "A14",     "b93c2d8", 95),
        t("A19", "Staff order queue UI",         "frontend", "progress", "A4",      "",        8),
        t("A20", "Reminder emails",              "signing",  "progress", "A9",      "",        41),
        t("A21", "Launch checklist run",         "backend",  "blocked",  "A18",     "",        300),
        t("A22", "Staging end-to-end suite",     "frontend", "todo",     "A17",     "",        0),
        t("A23", "Pre-launch QA pass",           "backend",  "todo",     "A22",     "",        0),
        t("A24", "Go-live",                      "signing",  "todo",     "A21,A23", "",        0)
      ],
      // The last six hours of each session: [startedMinutesAgo, endedMinutesAgo, state]
      timeline: {
        "harbor-orchestrator": [[360,200,"working"],[200,190,"idle"],[190,0,"working"]],
        "harbor-qa":           [[360,300,"working"],[300,285,"idle"],[285,140,"working"],[140,120,"idle"],[120,0,"working"]],
        "harbor-backend":      [[360,255,"working"],[255,240,"idle"],[240,60,"working"],[60,50,"idle"],[50,0,"working"]],
        "harbor-signing":      [[360,180,"working"],[180,150,"idle"],[150,41,"working"],[41,0,"quiet"]],
        "harbor-frontend":     [[360,300,"idle"],[300,95,"working"],[95,88,"idle"],[88,0,"working"]]
      },
      // Events on the timeline: [minutesAgo, session, kind, text]
      marks: [
        [210, "harbor-frontend", "READY", "A14 ready for QA, e0c58a4"],
        [175, "harbor-qa",       "PASS",  "A14 passed, suite 439/0"],
        [118, "harbor-backend",  "READY", "A18 ready for QA, b93c2d8"],
        [95,  "harbor-qa",       "FAIL",  "A18 failed: receipt total off by 1 cent"],
        [40,  "harbor-frontend", "READY", "A17 ready for QA, 7e1b4f6"],
        [25,  "harbor-backend",  "READY", "A15 ready for QA, 5d2a9c1"],
        [12,  "harbor-orchestrator", "START", "START TASK A16 sent to harbor-backend"]
      ]
    },
    {
      id: "meridian", name: "Meridian Model", client: "Internal",
      phase: "Phase 4 of 6", started: "12 Oct", target: "Wed 11 Nov",
      finding: "A full backtest on the 2024 backfill needs your go-ahead (about 40 min of CPU).",
      lanes: [
        { id: "data",     label: "Data",     hue: 28  },
        { id: "features", label: "Features", hue: 205 },
        { id: "models",   label: "Models",   hue: 150 }
      ],
      sessions: [
        { name: "meridian-chief",    role: "orchestrator", state: "working", seen: 2,  task: "Reviewing B12 handoff",             model: "Opus" },
        { name: "meridian-qa",       role: "qa",           state: "working", seen: 1,  task: "B12 roster-change features",        model: "Opus" },
        { name: "meridian-data",     role: "data",         state: "working", seen: 5,  task: "B14 backfill 2024 matches",         model: "Sonnet" },
        { name: "meridian-features", role: "features",     state: "idle",    seen: 12, task: "Waiting for the next assignment",   model: "Sonnet" },
        { name: "meridian-models",   role: "models",       state: "working", seen: 3,  task: "B13 odds against model comparison", model: "Sonnet" }
      ],
      tasks: [
        t("B1",  "Match results ingest",       "data",     "done",     "",     "2fa81c0", 9000),
        t("B2",  "Team ID reconciliation",     "data",     "done",     "B1",   "c7e5d31", 8800),
        t("B3",  "Map pool history",           "data",     "done",     "B1",   "18b9a4e", 8200),
        t("B4",  "Odds snapshot loader",       "data",     "done",     "B2",   "d02f6b7", 7600),
        t("B5",  "Player form features",       "features", "done",     "B2",   "6c1e08a", 7000),
        t("B6",  "Map-specific features",      "features", "done",     "B3",   "a49d7f2", 6400),
        t("B7",  "Rolling windows",            "features", "done",     "B5",   "3e8b15c", 5800),
        t("B8",  "Leakage canaries",           "features", "done",     "B7",   "f50a2d9", 5200),
        t("B9",  "Baseline model",             "models",   "done",     "B7",   "8d37c64", 4300),
        t("B10", "Calibration module",         "models",   "done",     "B9",   "b1e46f0", 3600),
        t("B11", "Walk-forward backtest",      "models",   "done",     "B10",  "70c9a8d", 2900),
        t("B12", "Roster-change features",     "features", "qa",       "B8",   "e93b5a1", 18),
        t("B13", "Odds against model comparison", "models", "progress", "B11",  "",        3),
        t("B14", "Backfill 2024 matches",      "data",     "progress", "B4",   "",        5),
        t("B15", "Ensemble stacking",          "models",   "todo",     "B13",  "",        0),
        t("B16", "Bankroll simulation",        "models",   "todo",     "B13",  "",        0),
        t("B17", "Live-ingest schedule",       "data",     "todo",     "B14",  "",        0),
        t("B18", "Final evaluation report",    "models",   "todo",     "B15,B16", "",     0)
      ],
      timeline: null, marks: []
    },
    {
      id: "lantern", name: "Lantern Reports", client: "Lantern Studio",
      phase: "Final review", started: "26 Oct", target: "Fri 30 Oct",
      finding: "Final report is ready for your review before it goes to the client.",
      lanes: [
        { id: "web",  label: "Web",  hue: 205 },
        { id: "data", label: "Data", hue: 28  }
      ],
      sessions: [
        { name: "lantern-org",  role: "orchestrator", state: "idle",    seen: 22,  task: "Waiting on your review of the report", model: "Opus" },
        { name: "lantern-qa",   role: "qa",           state: "gone",    seen: 125, task: "Session ended at a shell prompt",      model: "Opus" },
        { name: "lantern-web",  role: "web",          state: "working", seen: 6,   task: "C12 print stylesheet",                 model: "Sonnet" },
        { name: "lantern-data", role: "data",         state: "idle",    seen: 190, task: "All data tasks done",                  model: "Sonnet" }
      ],
      tasks: [
        t("C1",  "Report page shell",        "web",  "done", "",    "41d0e7b", 4200),
        t("C2",  "Spend data import",        "data", "done", "",    "9a6c3f5", 4100),
        t("C3",  "Channel breakdown table",  "web",  "done", "C2",  "d58b102", 3600),
        t("C4",  "Trend charts",             "web",  "done", "C2",  "07f4a9c", 3100),
        t("C5",  "Conversion funnel",        "web",  "done", "C2",  "e2c85d6", 2700),
        t("C6",  "Currency formatting",      "data", "done", "C2",  "5b1d9e3", 2500),
        t("C7",  "Period comparison",        "web",  "done", "C4",  "a83f6c1", 1900),
        t("C8",  "Annotations on spikes",    "web",  "done", "C4",  "16e0b7d", 1500),
        t("C9",  "Accessibility pass",       "web",  "done", "C7",  "c9a24f8", 900),
        t("C10", "Client view and sharing",  "web",  "done", "C9",  "7d5e130", 500),
        t("C11", "Report copy review",       "web",  "qa",   "C10", "f31b8a6", 31),
        t("C12", "Print stylesheet",         "web",  "progress", "C10", "",    6)
      ],
      timeline: null, marks: []
    }
  ];

  // Things only you can answer. Each belongs to one project and was raised by that project's orchestrator.
  var waiting = [
    { id: "w1", project: "harbor",   kind: "Decision", age: 190, from: "harbor-orchestrator",
      title: "Pick the layout for the /terms/ page",
      detail: "Three options for how the clinic accepts the terms. Task A6 is already done; this only changes the page copy and layout.",
      options: ["A  Single scrolling page", "B  Two steps with a summary", "C  Summary first, full text on request"],
      recommendation: "C. It matches how the paperwork flow already splits in two, and the summary keeps the page under one screen on a phone.",
      blocks: ["A21", "A24"] },
    { id: "w2", project: "harbor",   kind: "Decision", age: 70, from: "harbor-orchestrator",
      title: "Confirm the launch date with the client",
      detail: "Target is Fri 6 Nov. A18 is failing QA and A21 depends on it. The orchestrator estimates 1 working day if A18 passes tomorrow.",
      options: ["Keep Fri 6 Nov", "Move to Mon 9 Nov"],
      recommendation: "Keep Fri 6 Nov and re-check after A18 passes. Moving it now costs the client a week of notice.",
      blocks: ["A24"] },
    { id: "w3", project: "meridian", kind: "Approval", age: 58, from: "meridian-chief",
      title: "Run the full backtest on the 2024 backfill",
      detail: "About 40 minutes of CPU. The machine is also running the Harbor QA suite, so both will slow down.",
      options: ["Run now", "Run after 18:00"],
      recommendation: "Run after 18:00. Nothing downstream is waiting on it today.",
      blocks: ["B15", "B16"] },
    { id: "w4", project: "lantern",  kind: "Review",   age: 22, from: "lantern-org",
      title: "Review the final report before it goes to the client",
      detail: "C11 copy review is ready for QA but the QA session has ended. The orchestrator wants your read-through first.",
      options: ["Looks good, send", "Needs changes"],
      recommendation: "Read the summary page and the spend table; the rest is unchanged since the last review.",
      blocks: [] }
  ];

  // Latest first. Used for activity feeds.
  var events = [
    { min: 1,   project: "harbor",   who: "harbor-orchestrator", kind: "note",  text: "Loop tick: 3 working, 1 quiet (harbor-signing, 41 min)" },
    { min: 3,   project: "meridian", who: "meridian-models",     kind: "commit", text: "B13 wip: odds join, 4 tests", sha: "4be07a2" },
    { min: 8,   project: "harbor",   who: "harbor-frontend",     kind: "commit", text: "A19 queue list and filters", sha: "c61d3e9" },
    { min: 12,  project: "harbor",   who: "harbor-orchestrator", kind: "start", text: "START TASK A16 sent to harbor-backend" },
    { min: 18,  project: "meridian", who: "meridian-features",   kind: "ready", text: "B12 ready for QA", sha: "e93b5a1" },
    { min: 22,  project: "lantern",  who: "lantern-org",         kind: "ask",   text: "Needs you: review the final report" },
    { min: 25,  project: "harbor",   who: "harbor-backend",      kind: "ready", text: "A15 ready for QA", sha: "5d2a9c1" },
    { min: 31,  project: "lantern",  who: "lantern-web",         kind: "ready", text: "C11 ready for QA", sha: "f31b8a6" },
    { min: 40,  project: "harbor",   who: "harbor-frontend",     kind: "ready", text: "A17 ready for QA", sha: "7e1b4f6" },
    { min: 58,  project: "meridian", who: "meridian-chief",      kind: "ask",   text: "Needs you: approve the full backtest run" },
    { min: 95,  project: "harbor",   who: "harbor-qa",           kind: "fail",  text: "A18 failed: receipt total off by 1 cent", sha: "b93c2d8" },
    { min: 125, project: "lantern",  who: "lantern-qa",          kind: "gone",  text: "Session ended" },
    { min: 175, project: "harbor",   who: "harbor-qa",           kind: "pass",  text: "A14 passed, suite 439/0", sha: "e0c58a4" }
  ];

  // Derived figures. Everything on screen should come from these, never retyped.
  function stats(p) {
    var by = {}; STATES.forEach(function (s) { by[s.id] = 0; });
    p.tasks.forEach(function (x) { by[x.state] += 1; });
    var total = p.tasks.length;
    return { by: by, total: total, done: by.done, pct: Math.round(by.done / total * 100) };
  }
  projects.forEach(function (p) {
    p.stats = stats(p);
    p.waiting = waiting.filter(function (w) { return w.project === p.id; });
    p.sessionCounts = { working: 0, idle: 0, quiet: 0, gone: 0 };
    p.sessions.forEach(function (s) { p.sessionCounts[s.state] += 1; });
  });

  // Consistency checks. Read the console when you open a mockup.
  projects.forEach(function (p) {
    var sum = 0; for (var k in p.stats.by) sum += p.stats.by[k];
    console.assert(sum === p.tasks.length, p.id + ": task states must add up to the task total");
    p.tasks.forEach(function (x) {
      x.waits.forEach(function (w) {
        console.assert(p.tasks.some(function (y) { return y.id === w; }), p.id + ": " + x.id + " waits on unknown task " + w);
      });
    });
  });
  console.assert(projects[0].stats.total === 24 && projects[0].stats.done === 14, "Harbor Portal: 14 of 24 done");
  console.assert(projects[1].stats.total === 18 && projects[1].stats.done === 11, "Meridian Model: 11 of 18 done");
  console.assert(projects[2].stats.total === 12 && projects[2].stats.done === 10, "Lantern Reports: 10 of 12 done");
  console.assert(waiting.length === 4, "four items wait on the user");

  window.CONDUCTOR = {
    product: "Conductor", now: NOW, states: STATES, projects: projects, waiting: waiting, events: events,
    totals: {
      tasks: projects.reduce(function (a, p) { return a + p.stats.total; }, 0),
      done:  projects.reduce(function (a, p) { return a + p.stats.done; }, 0),
      waiting: waiting.length
    }
  };
})();
