<!-- The Automation Flow builder: the flow's header row over a canvas of its trigger and steps. -->
<template>
	<template v-if="flow.doc && !denied && !checking">
		<FlowHeader
			ref="header"
			v-model:title="flow.doc.title"
			v-model:enabled="flow.doc.enabled"
			:flow-name="flow.doc.name"
			:testing="testing"
			:unsaved="flow.unsaved || flow.isNew"
			:saving="flow.saving"
			:can-undo="flow.canUndo && !testing"
			:can-redo="flow.canRedo && !testing"
			@save="save"
			@toggle-test="toggleTest"
			@undo="flow.undo"
			@redo="flow.redo"
		/>
		<div
			v-if="flow.conflict"
			class="flex items-center justify-between gap-3 border-b bg-surface-amber-1 px-[--page-gutter] py-2 text-p-sm text-ink-amber-3"
			role="alert"
		>
			<span>{{ __("Someone else saved this flow after you opened it.") }}</span>
			<Button :label="__('Reload and discard my changes')" @click="flow.load()" />
		</div>
		<div class="flex min-h-0 flex-1 flex-col">
			<TrialRunBar
				v-if="testing"
				:trial="trial"
				:document-type="flow.doc.document_type"
				:can-test="canTest"
			/>
			<div class="flex min-h-0 flex-1" data-flow-body>
				<AutomationCanvas
					ref="canvas"
					class="min-w-0 flex-1"
					:nodes="shown.nodes"
					:edges="shown.edges"
					:selected-id="selectedId"
					:readonly="flow.saving || testing"
					:start-options="triggerGroups(flow.doc.document_type)"
					:block-options="blockGroups(flow.doc.document_type)"
					@select="selectedId = $event"
					@pick-start="pickStart"
					@add-node="addNode"
					@run-branch="runBranch"
				/>
				<aside
					v-if="!testing"
					class="h-full w-[340px] shrink-0 overflow-hidden border-l bg-surface-base"
					:aria-label="__('Inspector')"
				>
					<FlowInspector
						:doc="flow.doc"
						:selected-step="selectedStep"
						:targets="targetsFor(selectedStep)"
						@update="patchDoc"
						@remove="confirmRemoval"
					/>
				</aside>
			</div>
		</div>
	</template>
	<div
		v-else-if="denied || flow.failure"
		class="flex flex-1 flex-col items-center justify-center gap-3 px-8 text-center"
	>
		<p class="text-lg font-medium text-ink-gray-8">{{ failure.title }}</p>
		<p class="text-p-sm text-ink-gray-6">{{ failure.description }}</p>
		<Button v-if="failure.retry" :label="__('Try again')" @click="flow.load()" />
	</div>
	<div v-else class="flex flex-1 items-center justify-center">
		<LoadingIndicator class="size-5 text-ink-gray-5" />
	</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRouter } from "vue-router";
import { Button, LoadingIndicator, dialog, toast } from "frappe-ui";
import { __ } from "frappe/i18n";
import { AutomationCanvas } from "@framework/ui/AutomationCanvas";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { routeFor, useUnloadGuard } from "@shell";
import FlowHeader from "./FlowHeader.vue";
import TrialRunBar from "./TrialRunBar.vue";
import FlowInspector from "./inspector/FlowInspector.vue";
import { confirmDiscard } from "./flow/confirmDiscard";
import { FLOW_DOCTYPE, stepById } from "./flow/flowDoc";
import { failureState, notPermittedState } from "./flow/flowFailure";
import { handleShortcut } from "./flow/flowShortcuts";
import { blockGroups } from "./flow/workflowBlocks";
import { aliasTargets, loadCapabilities } from "./flow/workflowCapabilities";
import { workflowEdges, workflowNodes } from "./flow/workflowGraph";
import { insertAfter, newStep, removeStep, stepsBefore } from "./flow/workflowSteps";
import { triggerFromValue, triggerGroups } from "./flow/workflowTriggers";
import { useFlowDoc } from "./flow/useFlowDoc";
import { useTrialRun } from "./flow/useTrialRun";

const props = defineProps({
	doctype: { type: String, default: FLOW_DOCTYPE },
	name: { type: String, default: null },
	query: { type: Object, default: () => ({}) },
});

const router = useRouter();
const flow = useFlowDoc(props.name, props.query);
const permits = useDocPermissions(FLOW_DOCTYPE);
const header = ref(null);
const canvas = ref(null);
const selectedId = ref("");
const testing = ref(false);
const trial = useTrialRun(() => flow.doc);

const selectedStep = computed(() => stepById(flow.doc?.actions || [], selectedId.value));
const relationships = computed(() => parseList(flow.doc?.relationships));
const nodes = computed(() => workflowNodes(flow.doc, flow.errors));
const edges = computed(() => workflowEdges(flow.doc.actions));
const shown = computed(() =>
	testing.value
		? trial.decorate(nodes.value, edges.value)
		: { nodes: nodes.value, edges: edges.value }
);
// A trial runs the saved flow, so unsaved edits would not be what gets tested.
const canTest = computed(() => !!flow.doc?.name && !flow.isNew && !flow.unsaved);
// A new flow needs the create right; the insert checks again.
const checking = computed(() => !props.name && permits.loading.value);
const denied = computed(() => !props.name && !checking.value && !permits.holds("create"));
const failure = computed(() => (denied.value ? notPermittedState() : failureState(flow.failure)));

flow.load();
watch(
	() => props.name,
	(name) => name !== flow.current() && flow.load(name)
);
watch(
	() => props.name,
	(name, previous) => {
		// A new flow keeps its test bar through the first save, which names it.
		if (!previous) return;
		testing.value = false;
		trial.close();
	}
);
watch(() => flow.doc?.document_type, loadOffers, { immediate: true });
watch(
	() => aliasTargets(flow.doc?.document_type, relationships.value, []).map((t) => t.doctype),
	(doctypes) => doctypes.forEach(loadOffers),
	{ immediate: true }
);

watch(
	() => targetsFor(selectedStep.value).map((target) => target.doctype),
	(doctypes) => doctypes.forEach(loadOffers)
);

useUnloadGuard(() => flow.unsaved);
onBeforeRouteLeave(() => !flow.unsaved || confirmDiscard());
onBeforeRouteUpdate((to) => to.params.name === props.name || !flow.unsaved || confirmDiscard());
onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));

async function loadOffers(doctype) {
	if (!doctype) return;
	try {
		await loadCapabilities(doctype);
	} catch {
		toast.error(__("The triggers and actions of {0} could not be loaded", [doctype]));
	}
}

function onKeydown(event) {
	handleShortcut(event, { save, undo: whenEditing(flow.undo), redo: whenEditing(flow.redo) });
}

// The outcomes sit on the nodes the run saw, so an edit mid-test would move them.
function whenEditing(edit) {
	return () => !testing.value && edit();
}

function runBranch(branch) {
	if (canTest.value) trial.runBranch(branch);
}

async function save() {
	if (!flow.doc) return;
	const wasNew = flow.isNew;
	if (!flow.doc.title?.trim()) header.value?.focusTitle();
	if (await flow.save()) {
		if (wasNew) router.replace(routeFor(FLOW_DOCTYPE, flow.doc.name));
	}
}

function toggleTest() {
	testing.value = !testing.value;
	if (!testing.value) trial.close();
}

// The bar changes the canvas's height, and the view keeps the size it was fitted to.
watch(
	() => [testing.value, canTest.value, !!trial.summary || !!trial.error, trial.detailsOpen],
	async () => {
		await nextTick();
		canvas.value?.fitView();
	}
);

function pickStart(value) {
	patchDoc(triggerFromValue(value));
	selectedId.value = "trigger";
}

/** The inspector reports its edits; the page owns the document. */
function patchDoc(values) {
	Object.assign(flow.doc, values);
}

/** Every alias a step can target: the trigger record, relationships and earlier outputs. */
function targetsFor(step) {
	if (!step) return [];
	return aliasTargets(
		flow.doc.document_type,
		relationships.value,
		stepsBefore(flow.doc.actions, step)
	);
}

function confirmRemoval() {
	const trigger = !selectedStep.value;
	dialog.danger({
		title: trigger ? __("Delete trigger") : __("Delete step"),
		message: trigger
			? __("This removes the trigger and all steps of the flow.")
			: __("Are you sure you want to delete this step?"),
		confirmLabel: __("Delete"),
		onConfirm: ({ close }) => {
			if (trigger) Object.assign(flow.doc, { ...emptyTrigger(), actions: [] });
			else removeStep(flow.doc.actions, selectedStep.value);
			selectedId.value = "trigger";
			close();
		},
	});
}

function addNode({ afterId, branch, value }) {
	const block = blockGroups(flow.doc.document_type)
		.flatMap((group) => group.options)
		.find((option) => option.value === value);
	if (!block) return;
	const step = newStep(block.values);
	const after = afterId && stepById(flow.doc.actions, afterId);
	if (after && branch) after.children[branch].push(step);
	else if (after) insertAfter(flow.doc.actions, after, step);
	else flow.doc.actions.unshift(step);
	selectedId.value = step._id;
}

function emptyTrigger() {
	return {
		trigger_type: "",
		trigger_field: "",
		from_value: "",
		to_value: "",
		custom_event: "",
		date_field: "",
		date_offset: 0,
		date_direction: "Before",
		cron_expression: "",
		filters: "[]",
		condition: "",
		relationships: "[]",
	};
}

function parseList(value) {
	try {
		const parsed = typeof value === "string" ? JSON.parse(value || "[]") : value;
		return Array.isArray(parsed) ? parsed : [];
	} catch {
		return [];
	}
}
</script>
