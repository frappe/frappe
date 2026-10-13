import { computed, reactive } from "vue";

import { runsByUserMessage } from "./api/runs.js";

// The records boot lists; the page keeps its copy until one of them is saved or deleted.
const BOOT_DOCTYPES = new Set(["Flow Model", "Flow Agent"]);

// What the page keeps beside the chat store: the boot data, the agent a new chat starts
// with, the settings tab to open, and each session's Flow Runs and run log (for per-turn
// feedback). `refresh` re-fetches boot when a record it lists changes; `sync` re-reads a
// session's runs.
export function createPage(boot, { refresh = () => {}, sync = () => {} } = {}) {
	const runIndexes = new Map();
	const state = reactive({
		boot,
		agent: defaultAgent(boot),
		runs: {}, // session → Flow Run rows as the server last reported them
		readOnly: {}, // session → true when the user may view it but not write to it
		log: {}, // session → durable log rows, slimmed to what run mapping needs
		settingsTab: "general", // the settings dialog opens on this tab
	});

	function can(doctype, ptype) {
		return (state.boot.permissions?.[doctype] ?? []).includes(ptype);
	}

	function onBoot(boot) {
		state.boot = { ...state.boot, ...boot };
		if (!boot.agents.some((agent) => agent.name === state.agent))
			state.agent = defaultAgent(boot);
	}

	function onSession(payload) {
		state.runs[payload.name] = payload.runs ?? [];
		state.readOnly[payload.name] = Boolean(payload.read_only);
	}

	function onRows(sid, rows, { replace }) {
		// a sub-agent's rows belong to its own thread, not to a run
		const slim = rows
			.filter((row) => typeof row.seq === "number" && !row.subagent_id)
			.map(({ type, seq, run_id, reason }) => ({ type, seq, run_id, reason }));
		state.log[sid] = replace ? slim : [...(state.log[sid] ?? []), ...slim];
		// a chat opened as its run ended: the stream starts past that run_ended, so sync here
		if (
			replace &&
			slim.at(-1)?.type === "run_ended" &&
			state.runs[sid]?.some((run) => run.status === "Running")
		)
			sync(sid);
	}

	// turn keys are "turn:<seq of the user message>"
	function runForTurn(sid, turnKey) {
		const seq = Number(turnKey?.split(":")[1]);
		if (!Number.isFinite(seq)) return null;
		if (!runIndexes.has(sid))
			runIndexes.set(
				sid,
				computed(() => runsByUserMessage(state.log[sid] ?? [], state.runs[sid] ?? []))
			);
		return runIndexes.get(sid).value.get(seq) ?? null;
	}

	function updateRun(sid, name, fields) {
		const run = (state.runs[sid] ?? []).find((row) => row.name === name);
		if (run) Object.assign(run, fields);
	}

	// the settings forms report every save and delete; only boot's own doctypes matter
	function changed(doctype) {
		if (BOOT_DOCTYPES.has(doctype)) refresh();
	}

	return { state, can, onBoot, onSession, onRows, runForTurn, updateRun, changed };
}

function defaultAgent(boot) {
	return boot.default_agent ?? boot.agents?.[0]?.name ?? null;
}
