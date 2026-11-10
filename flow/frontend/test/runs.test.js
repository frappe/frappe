import assert from "node:assert/strict";
import test from "node:test";

import { matchRuns, runsByUserMessage, runSpans } from "../src/api/runs.js";

const started = (seq, run_id) => ({ type: "run_started", seq, run_id });
const ended = (seq, reason = "done") => ({ type: "run_ended", seq, reason });
const user = (seq) => ({ type: "user_message", seq });

test("a run spans run_started to run_ended; a resume after a pause continues it, unless a cancelled batch came between", () => {
	const cases = [
		[
			[started(1, "a"), user(2), ended(5), started(6, "b"), user(7)],
			[
				{ startSeq: 1, endSeq: 5, runIds: ["a"] },
				{ startSeq: 6, endSeq: null, runIds: ["b"] },
			],
		],
		[
			[started(1, "a"), user(2), ended(4, "paused"), started(5, "a2"), ended(9)],
			[{ startSeq: 1, endSeq: 9, runIds: ["a", "a2"] }],
		],
		[
			[
				started(1, "a"),
				user(2),
				ended(4, "paused"),
				{ type: "tool_result", seq: 5 },
				started(6, "b"),
				user(7),
			],
			[
				{ startSeq: 1, endSeq: 4, runIds: ["a"] },
				{ startSeq: 6, endSeq: null, runIds: ["b"] },
			],
		],
	];
	for (const [rows, spans] of cases) assert.deepEqual(runSpans(rows), spans);
});

test("synced rows match by their daemon run id, the rest by order", () => {
	const spans = runSpans([
		started(1, "a"),
		ended(3),
		started(4, "b"),
		ended(6),
		started(7, "c"),
	]);
	const names = (runs) => matchRuns(spans, runs).map((run) => (run ? run.name : null));
	const R1 = { name: "R1", daemon_run_id: "a" };
	assert.deepEqual(
		names([R1, { name: "R2", daemon_run_id: null }, { name: "R3", daemon_run_id: null }]),
		["R1", "R2", "R3"]
	);
	// a row synced later names its segment even when the order disagrees
	assert.deepEqual(names([{ name: "R2", daemon_run_id: "b" }, R1]), ["R1", "R2", null]);
	// "b" was rewound off the branch before "c" started: only the unsynced R3 may take it
	const rewound = runSpans([started(1, "a"), user(2), ended(3), started(6, "c"), user(7)]);
	const runs = [R1, { name: "R2", daemon_run_id: "b" }, { name: "R3", daemon_run_id: null }];
	assert.deepEqual(matchRuns(rewound, runs), [runs[0], runs[2]]);
});

test("a turn finds its run by its user message position", () => {
	const rows = [started(1, "a"), user(2), ended(5), started(6, "b"), user(7), user(8)];
	const runs = [
		{ name: "R1", daemon_run_id: "a" },
		{ name: "R2", daemon_run_id: "b" },
	];
	assert.equal(runsByUserMessage(rows, runs).get(2).name, "R1");
	assert.equal(runsByUserMessage(rows, runs).get(7).name, "R2");
	assert.equal(runsByUserMessage(rows, runs).get(8).name, "R2"); // a steered message joins the run
	assert.equal(runsByUserMessage(rows, runs).get(0), undefined);

	// a model or thinking change while paused keeps the resumed run on its turn
	const paused = [
		started(1, "a"),
		user(2),
		ended(4, "paused"),
		{ type: "model_changed", seq: 5 },
		started(6, "a2"),
		ended(9),
	];
	const resumed = { name: "R1", daemon_run_id: "a2" };
	const spare = { name: "R2", daemon_run_id: null };
	assert.equal(runsByUserMessage(paused, [resumed, spare]).get(2), resumed);
});

test("feedback lookups share the session scan and update when rows or runs change", async () => {
	const { createPage } = await import("../src/page.js");
	const page = createPage({ agents: [] });
	const rows = [started(1, "a"), user(2), ended(5), started(6, "b"), user(7)];
	page.onRows("s", rows, { replace: true });
	page.onSession({ name: "s", runs: [{ name: "R1", daemon_run_id: "a" }] });
	let scans = 0;
	Object.defineProperty(page.state.log.s[0], "type", {
		get() {
			scans++;
			return "run_started";
		},
	});
	for (let i = 0; i < 100; i++) assert.equal(page.runForTurn("s", "turn:2").name, "R1");
	assert.ok(scans < 10, `the same log row was read ${scans} times`);
	assert.equal(page.runForTurn("s", "turn:7"), null);
	page.onSession({
		name: "s",
		runs: [
			{ name: "R1", daemon_run_id: "a" },
			{ name: "R2", daemon_run_id: "b" },
		],
	});
	assert.equal(page.runForTurn("s", "turn:7").name, "R2");
	page.updateRun("s", "R2", { feedback_rating: "Up" });
	assert.equal(page.runForTurn("s", "turn:7").feedback_rating, "Up");
	page.onRows("s", [user(8)], { replace: false });
	assert.equal(page.runForTurn("s", "turn:8").name, "R2");
	page.onRows("s", [started(1, "b"), user(2)], { replace: true });
	assert.equal(page.runForTurn("s", "turn:2").name, "R2");
	assert.equal(page.runForTurn("s", "turn:7"), null);

	// a sub-agent's rows belong to its own thread, not to a run
	const child = { subagent_id: "c1" };
	page.onRows(
		"s",
		[
			started(1, "a"),
			user(2),
			{ ...started(3, "a-c1"), ...child },
			{ ...user(4), ...child },
			{ ...ended(5, "paused"), ...child },
			{ ...started(6, "a-c2"), ...child },
			{ ...ended(7), ...child },
			ended(9),
			started(10, "b"),
			user(11),
		],
		{ replace: true }
	);
	page.onSession({ name: "s", runs: [{ name: "R1" }, { name: "R2" }] });
	assert.equal(page.state.log.s.length, 5);
	assert.equal(page.runForTurn("s", "turn:2").name, "R1");
	assert.equal(page.runForTurn("s", "turn:4"), null);
	assert.equal(page.runForTurn("s", "turn:11").name, "R2");
});

test("a chat opened just as its run ended syncs it, since its stream starts past that row", async () => {
	const { createPage } = await import("../src/page.js");
	const synced = [];
	const page = createPage({ agents: [] }, { sync: (sid) => synced.push(sid) });
	const rows = [started(1, "a"), user(2), ended(5)];
	page.onSession({ name: "s", runs: [{ name: "R1", daemon_run_id: "a", status: "Running" }] });
	page.onRows("s", rows, { replace: true });
	assert.deepEqual(synced, ["s"]);
	// a live row is the stream's to report; a run still going or settled needs nothing
	page.onRows("s", [ended(6)], { replace: false });
	page.onRows("s", rows.slice(0, 2), { replace: true });
	page.onSession({ name: "s", runs: [{ name: "R1", daemon_run_id: "a", status: "Completed" }] });
	page.onRows("s", rows, { replace: true });
	assert.deepEqual(synced, ["s"]);
});
