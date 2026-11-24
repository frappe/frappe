<template class="bg-surface-base">
	<div class="flex h-full min-h-0 flex-col gap-3">
		<div class="flex items-end gap-2">
			<div class="min-w-0 flex-1 space-y-1.5">
				<Link
					v-if="doc.document_type"
					class="max-w-sm"
					variant="outline"
					:model-value="docname"
					:doctype="doc.document_type"
					:label="__('Select a record')"
					:placeholder="__('Pick a {0}', [doc.document_type])"
					@update:model-value="pickDocument"
				/>
			</div>
			<Button v-if="playing" :label="__('Skip')" variant="subtle" @click="finishPlayback" />
			<Button
				:label="__('Start test run')"
				variant="solid"
				icon-left="lucide-play"
				:loading="running"
				:disabled="doc.document_type && !docname"
				@click="run()"
			/>
		</div>

		<div v-if="error" class="text-sm text-ink-red-4" role="alert">
			{{ error }}
		</div>

		<div
			v-if="summary"
			class="flex items-center gap-2 rounded-6 border border-outline-gray-2 bg-surface-gray-1 px-3 py-2"
		>
			<Badge
				:label="__(playing ? 'Running' : summary.status)"
				:theme="playing ? 'blue' : STATUS_THEMES[summary.status] || 'gray'"
				variant="subtle"
			/>
			<span class="shrink-0 text-sm text-ink-gray-6">
				{{ __("{0} of {1} steps ran", [ranCount, stepCount]) }}
			</span>
			<span v-if="summary.error_summary" class="truncate text-sm text-ink-red-4">
				{{ summary.error_summary }}
			</span>
			<Button
				v-if="failures.length"
				class="ml-auto shrink-0"
				variant="ghost"
				size="sm"
				:label="showFailures ? __('Hide details') : __('Show details')"
				@click="showFailures = !showFailures"
			/>
		</div>

		<div
			v-if="showFailures && failures.length"
			class="max-h-40 shrink-0 space-y-2 overflow-y-auto rounded-6 border border-outline-red-2 p-3"
		>
			<div v-for="step in failures" :key="step.step_key" class="space-y-1">
				<div class="text-sm-medium text-ink-gray-8">{{ stepLabel(step) }}</div>
				<div v-if="step.message" class="text-xs text-ink-red-4">
					{{ step.message }}
				</div>
				<pre v-if="traceOf(step)" class="overflow-x-auto text-xs text-ink-gray-6">{{
					traceOf(step)
				}}</pre>
			</div>
		</div>

		<div class="min-h-0 flex-1 overflow-hidden rounded-6 border border-outline-gray-2">
			<AutomationCanvas :nodes="nodes" :edges="edges" readonly @run-branch="runBranch" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { translate as __ } from "../../utils/translate";
import { Link } from "../Link";
import AutomationCanvas from "../AutomationCanvas/AutomationCanvas.vue";
import { workflowEdges, workflowNodes } from "./graph";
import { armLabels, isBranching, toRows } from "./steps";
import { Badge, Button, call } from "frappe-ui";
import { computed, onUnmounted, reactive, ref } from "vue";

const props = defineProps({
	automationName: { type: String, default: "" },
	doc: { type: Object, required: true },
});

const STATUS_THEMES = {
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

const docname = ref("");
const running = ref(false);
const playing = ref(false);
const showFailures = ref(false);
const error = ref("");
const summary = ref(null);
const activeKey = ref("");
const outcomes = reactive({});
const taken = reactive({});
const overrides = reactive({});

let result = null;
let playToken = 0;

onUnmounted(() => (playToken += 1));

const finished = computed(() => Boolean(summary.value) && !playing.value);

/** Trace entries are keyed by step key; branch arms by the row index of their `If`. */
const rowIdx = computed(() => {
	const map = {};
	toRows(props.doc.actions || []).forEach((row) => (map[row.step_key] = row.idx));
	return map;
});

/** Every step, with the arm it sits in resolved against the arm the run took. */
const states = computed(() => walkStates(props.doc.actions || [], false, new Map()));

const stepKeys = computed(
	() => new Set([...states.value.values()].map(({ node }) => node.step_key))
);

const nodes = computed(() =>
	workflowNodes(props.doc).map((node) => (node.data.start ? triggerNode(node) : stepNode(node)))
);

const edges = computed(() =>
	workflowEdges(props.doc.actions).map((edge) =>
		states.value.get(edge.target)?.offPath ? offPathEdge(edge) : edge
	)
);

const stepCount = computed(() => states.value.size);

const ranCount = computed(
	() => Object.keys(outcomes).filter((key) => stepKeys.value.has(key)).length
);

const failures = computed(() =>
	Object.values(outcomes).filter((step) => step.status === "Failed")
);

function walkStates(nodes, offPath, states) {
	nodes.forEach((node) => {
		states.set(node._id, { node, offPath });
		if (!isBranching(node)) return;
		const chosen = taken[String(branchIdx(node))];
		["If", "Else"].forEach((arm) =>
			walkStates(node.children[arm], offPath || Boolean(chosen && chosen !== arm), states)
		);
	});
	return states;
}

/** The `If` row that decides a node's arms - for a wait, the outcome row folded into it. */
function branchIdx(node) {
	return rowIdx.value[node._outcomeKey || node.step_key];
}

function triggerNode(node) {
	return {
		...node,
		data: { ...node.data, detail: docname.value || node.data.detail },
	};
}

function stepNode(node) {
	const step = states.value.get(node.id).node;
	const outcome = outcomes[step.step_key];
	return {
		...node,
		data: {
			...node.data,
			run: runState(step, outcome),
			detail: outcome ? outcome.message || outcome.detail : node.data.detail,
			dimmed: states.value.get(node.id)?.offPath || (finished.value && !outcome),
		},
	};
}

function runState(step, outcome) {
	const status = activeKey.value === step.step_key ? "running" : outcome?.status;
	if (!status) return undefined;
	return {
		status,
		forced: Boolean(overrides[String(branchIdx(step))]),
		retryArms: retryArms(step),
		durationMs: outcome?.duration_ms,
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

/** A run that fell over before its first step records itself against a `setup` key. */
function stepLabel(step) {
	return step.step_key === "setup" ? __("Before the first step") : step.step_key;
}

/** A step failure carries a traceback of its own; a setup failure only has its detail. */
function traceOf(step) {
	return step.traceback || (step.message ? "" : step.detail);
}

function offPathEdge(edge) {
	return {
		...edge,
		style: { stroke: "var(--outline-gray-3)", strokeDasharray: "4 4" },
	};
}

function pickDocument(value) {
	docname.value = value;
	reset();
}

function reset() {
	playToken += 1;
	playing.value = false;
	showFailures.value = false;
	activeKey.value = "";
	summary.value = null;
	result = null;
	Object.keys(outcomes).forEach((key) => delete outcomes[key]);
	Object.keys(taken).forEach((key) => delete taken[key]);
}

function runBranch({ nodeId, arm }) {
	overrides[String(branchIdx(states.value.get(nodeId).node))] = arm.key;
	run({ keepOverrides: true });
}

async function run({ keepOverrides = false } = {}) {
	reset();
	if (!keepOverrides) clearOverrides();
	running.value = true;
	error.value = "";
	try {
		result = await call("frappe.automation_engine.api.trial_run", {
			automation: props.automationName,
			docname: docname.value || null,
			branch_overrides: { ...overrides },
		});
		await playback(result);
	} catch (e) {
		error.value = plainText(e.messages?.join("\n") || e.message);
	} finally {
		running.value = false;
	}
}

/** Server messages carry markup - a doc link on the server-scripts error, say. */
function plainText(message) {
	const holder = document.createElement("div");
	holder.innerHTML = String(message || "");
	return holder.textContent.trim();
}

function clearOverrides() {
	Object.keys(overrides).forEach((key) => delete overrides[key]);
}

/** Reveal the trace a step at a time, holding each node for as long as it took to run. */
async function playback(run) {
	const token = ++playToken;
	summary.value = run;
	playing.value = true;
	for (const entry of run.steps || []) {
		if (stepKeys.value.has(entry.step_key)) {
			activeKey.value = entry.step_key;
			await hold(holdFor(entry));
			if (token !== playToken) return;
		}
		reveal(entry, run);
	}
	activeKey.value = "";
	playing.value = false;
}

/** Jump to the end: the trace is already in hand, so nothing is lost by not watching it. */
function finishPlayback() {
	playToken += 1;
	(result?.steps || []).forEach((entry) => reveal(entry, result));
	activeKey.value = "";
	playing.value = false;
}

function reveal(entry, run) {
	outcomes[entry.step_key] = entry;
	const branch = run.branches?.[String(entry.step_idx + 1)];
	if (branch) taken[String(entry.step_idx + 1)] = branch;
}

function holdFor(entry) {
	const type = entry.action_type;
	if (type === "Wait" || type === "WaitForEvent") return WAIT_HOLD;
	return Math.min(Math.max(entry.duration_ms || 0, MIN_HOLD), MAX_HOLD);
}

function hold(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}
</script>
