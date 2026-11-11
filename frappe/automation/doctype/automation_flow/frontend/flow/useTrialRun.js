// A trial run of the saved flow, played back on the canvas one step at a time.
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import { __ } from "frappe/i18n";
import { isApiError, runMethod } from "@framework/ui/api";
import { htmlToText } from "@framework/ui/RichText";
import { stepById } from "./flowDoc";
import { armLabels, isBranching, toRows } from "./workflowSteps";

export const STATUS_THEMES = {
	Success: "green",
	Skipped: "gray",
	Waiting: "blue",
	Failed: "red",
	"Partially Failed": "amber",
};

// A wait is reported instantly by the server; the pause is here so the run reads as a sequence.
const WAIT_HOLD = 5000;
const MIN_HOLD = 400;
const MAX_HOLD = 1500;

/** `getDoc` returns the flow document the canvas draws; the trial runs its saved copy. */
export function useTrialRun(getDoc) {
	const docname = ref("");
	const running = ref(false);
	const playing = ref(false);
	const error = ref("");
	const summary = ref(null);
	const activeKey = ref("");
	const outcomes = reactive({});
	const taken = reactive({});
	const overrides = reactive({});
	let result = null;
	let playToken = 0;

	onBeforeUnmount(() => (playToken += 1));

	const finished = computed(() => Boolean(summary.value) && !playing.value);
	const steps = computed(() => walkSteps(getDoc().actions || [], false, new Map()));
	const stepCount = computed(() => steps.value.size);
	const ranCount = computed(
		() => Object.keys(outcomes).filter((key) => keyed.value.has(key)).length
	);
	const keyed = computed(
		() => new Set([...steps.value.values()].map(({ node }) => node.step_key))
	);
	const failures = computed(() =>
		Object.values(outcomes).filter((step) => step.status === "Failed")
	);
	// Trace entries are keyed by step key; an arm is keyed by the row index of its `If`.
	const rowIdx = computed(() => {
		const map = {};
		toRows(getDoc().actions || []).forEach((row) => (map[row.step_key] = row.idx));
		return map;
	});

	/** Every step, with the arm it sits in resolved against the arm the run took. */
	function walkSteps(nodes, offPath, found) {
		nodes.forEach((node) => {
			found.set(node._id, { node, offPath });
			if (!isBranching(node)) return;
			const chosen = taken[String(branchIdx(node))];
			["If", "Else"].forEach((arm) =>
				walkSteps(node.children[arm], offPath || Boolean(chosen && chosen !== arm), found)
			);
		});
		return found;
	}

	/** The `If` row that decides a node's arms: for a wait, the outcome row folded into it. */
	function branchIdx(node) {
		return rowIdx.value[node._outcomeKey || node.step_key];
	}

	/** The canvas nodes and edges with the run laid over them. */
	function decorate(nodes, edges) {
		return {
			nodes: nodes.map((node) =>
				node.id === "trigger" ? triggerNode(node) : stepNode(node)
			),
			edges: edges.map((edge) =>
				steps.value.get(edge.target)?.offPath ? offPathEdge(edge) : edge
			),
		};
	}

	function triggerNode(node) {
		return { ...node, data: { ...node.data, detail: docname.value || node.data.detail } };
	}

	function stepNode(node) {
		const step = steps.value.get(node.id)?.node;
		if (!step) return node;
		const outcome = outcomes[step.step_key];
		const status = activeKey.value === step.step_key ? "running" : outcome?.status;
		return {
			...node,
			data: {
				...node.data,
				detail: outcome
					? outcome.message || outcome.detail || node.data.detail
					: node.data.detail,
				dimmed: steps.value.get(node.id).offPath || (finished.value && !outcome),
				run: status && {
					status,
					forced: Boolean(overrides[String(branchIdx(step))]),
					retryArms: retryArms(step),
					durationMs: outcome?.duration_ms,
				},
			},
		};
	}

	/** The arm this record did not reach, offered so the other path can still be tried. */
	function retryArms(step) {
		const chosen = taken[String(branchIdx(step))];
		if (!isBranching(step) || !chosen || !finished.value) return [];
		const labels = armLabels(step);
		return ["If", "Else"]
			.filter((arm) => arm !== chosen && step.children[arm].length)
			.map((arm) => ({ key: arm, label: labels[arm] }));
	}

	function offPathEdge(edge) {
		return { ...edge, style: { ...edge.style, stroke: "#C7C7C7", strokeDasharray: "4 4" } };
	}

	function pickDocument(value) {
		docname.value = value || "";
		reset();
	}

	function reset() {
		playToken += 1;
		playing.value = false;
		activeKey.value = "";
		summary.value = null;
		error.value = "";
		result = null;
		clear(outcomes);
		clear(taken);
	}

	/** Back to a blank canvas, with the picked record forgotten too. */
	function close() {
		reset();
		clear(overrides);
		docname.value = "";
	}

	function runBranch({ nodeId, arm }) {
		const step = stepById(getDoc().actions || [], nodeId);
		if (!step) return;
		overrides[String(branchIdx(step))] = arm.key;
		run({ keepOverrides: true });
	}

	async function run({ keepOverrides = false } = {}) {
		reset();
		if (!keepOverrides) clear(overrides);
		running.value = true;
		try {
			const { data } = await runMethod("frappe.automation_engine.api.trial_run", {
				automation: getDoc().name,
				docname: docname.value || null,
				branch_overrides: { ...overrides },
			});
			result = data;
			await playback(data);
		} catch (e) {
			error.value = isApiError(e) ? htmlToText(e.message) : e.message;
		} finally {
			running.value = false;
		}
	}

	/** Reveal the trace a step at a time, holding each node for as long as it took to run. */
	async function playback(trace) {
		const token = ++playToken;
		summary.value = trace;
		playing.value = true;
		for (const entry of trace.steps || []) {
			if (keyed.value.has(entry.step_key)) {
				activeKey.value = entry.step_key;
				await hold(holdFor(entry));
				if (token !== playToken) return;
			}
			reveal(entry, trace);
		}
		activeKey.value = "";
		playing.value = false;
	}

	/** Jump to the end: the trace is already in hand, so nothing is lost by not watching it. */
	function skip() {
		playToken += 1;
		(result?.steps || []).forEach((entry) => reveal(entry, result));
		activeKey.value = "";
		playing.value = false;
	}

	function reveal(entry, trace) {
		outcomes[entry.step_key] = entry;
		const branch = trace.branches?.[String(entry.step_idx + 1)];
		if (branch) taken[String(entry.step_idx + 1)] = branch;
	}

	return reactive({
		docname,
		running,
		playing,
		error,
		summary,
		failures,
		stepCount,
		ranCount,
		pickDocument,
		decorate,
		runBranch,
		run,
		skip,
		close,
	});
}

function holdFor(entry) {
	if (entry.action_type === "Wait" || entry.action_type === "WaitForEvent") return WAIT_HOLD;
	return Math.min(Math.max(entry.duration_ms || 0, MIN_HOLD), MAX_HOLD);
}

function hold(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

function clear(target) {
	Object.keys(target).forEach((key) => delete target[key]);
}

/** A run that fell over before its first step records itself against a `setup` key. */
export function stepLabel(step) {
	return step.step_key === "setup" ? __("Before the first step") : step.step_key;
}

/** A step failure carries a traceback of its own; a setup failure only has its detail. */
export function traceOf(step) {
	return step.traceback || (step.message ? "" : step.detail);
}
