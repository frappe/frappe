import { computed, reactive, watch } from "vue";

import { runsByUserMessage } from "./api/runs.js";

// The records boot reports on; the page keeps its copy until one of them is saved or deleted.
const BOOT_DOCTYPES = new Set(["Flow Model", "Flow Agent", "Flow Provider"]);

// What the page keeps beside the chat store: the boot data, the agent a new chat starts
// with, the settings tab to open, and each session's Flow Runs and run log (for per-turn
// feedback). `refresh` re-fetches boot when a record it lists changes; `sync` re-reads a
// session's runs; `renamedModel` passes a model's new name on to the chat store;
// `reloadSkills` re-reads the skills a chat may start. With a `storageKey`, the agent
// outlasts a reload.
export function createPage(
	boot,
	{
		storageKey = null,
		refresh = () => {},
		sync = () => {},
		renamedModel = () => {},
		reloadSkills = () => {},
	} = {}
) {
	const runIndexes = new Map();
	const agentKey = storageKey && `${storageKey}.agent`;
	const saved = agentKey && readItem(agentKey);
	const state = reactive({
		boot,
		agent: boot.agents?.some((agent) => agent.name === saved) ? saved : defaultAgent(boot),
		runs: {}, // session → Flow Run rows as the server last reported them
		readOnly: {}, // session → true when the user may view it but not write to it
		owner: {}, // session → the user who owns it, the only one who shares it
		generalAccess: {}, // session → "Restricted", or "Everyone" when any Flow user may view
		log: {}, // session → durable log rows, slimmed to what run mapping needs
		settingsTab: null, // the tab settings open on: null for the first, or a narrow page's list
	});
	if (agentKey)
		watch(
			() => state.agent,
			(agent) => agent && writeItem(agentKey, agent)
		);

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
		state.owner[payload.name] = { name: payload.owner, full_name: payload.owner_name };
		state.generalAccess[payload.name] = payload.general_access;
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

	// the settings forms report every save and delete; boot's own doctypes refetch it, and a
	// skill or an agent's list of them changes what a chat may start
	function changed(doctype) {
		if (BOOT_DOCTYPES.has(doctype)) refresh();
		if (doctype === "Flow Skill" || doctype === "Flow Agent") reloadSkills();
	}

	// a setup step's "Add a model": settings on that tab, on a blank record its panel takes once
	let newRecord = null;
	function createRecord(key) {
		newRecord = key;
		state.settingsTab = key;
	}
	function takeNewRecord(key) {
		const asked = newRecord === key;
		if (asked) newRecord = null;
		return asked;
	}

	// a renamed agent or model stays the one a new chat starts with
	function renamed(doctype, from, to) {
		if (doctype === "Flow Agent" && state.agent === from) state.agent = to;
		if (doctype === "Flow Model") renamedModel(from, to);
	}

	return {
		state,
		can,
		onBoot,
		onSession,
		onRows,
		runForTurn,
		updateRun,
		changed,
		renamed,
		createRecord,
		takeNewRecord,
	};
}

function defaultAgent(boot) {
	return boot.default_agent ?? boot.agents?.[0]?.name ?? null;
}

// blocked or full site data refuses storage; the page then just doesn't remember the agent
function readItem(key) {
	try {
		return localStorage.getItem(key);
	} catch {
		return null;
	}
}

function writeItem(key, value) {
	try {
		localStorage.setItem(key, value);
	} catch {
		// not saved: the next load starts on the default agent
	}
}
