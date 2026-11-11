<!-- The Automation Flow builder: the flow's header row over a canvas of its trigger and steps. -->
<template>
	<template v-if="flow.doc && !denied && !checking">
		<FlowHeader
			ref="header"
			v-model:title="flow.doc.title"
			v-model:enabled="flow.doc.enabled"
			:unsaved="flow.unsaved || flow.isNew"
			:saving="flow.saving"
			:can-undo="flow.canUndo"
			:can-redo="flow.canRedo"
			@save="save"
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
		<div class="flex min-h-0 flex-1" data-flow-body>
			<AutomationCanvas
				ref="canvas"
				class="min-w-0 flex-1"
				:nodes="nodes"
				:edges="edges"
				:selected-id="selectedId"
				:readonly="flow.saving"
				:start-options="triggerGroups(flow.doc.document_type)"
				:block-options="blockGroups(flow.doc.document_type)"
				@select="selectedId = $event"
				@pick-start="pickStart"
				@add-node="addNode"
			/>
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRouter } from "vue-router";
import { Button, LoadingIndicator, toast } from "frappe-ui";
import { __ } from "frappe/i18n";
import { AutomationCanvas } from "@framework/ui/AutomationCanvas";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { routeFor, useUnloadGuard } from "@shell";
import FlowHeader from "./FlowHeader.vue";
import { confirmDiscard } from "./flow/confirmDiscard";
import { FLOW_DOCTYPE, stepById } from "./flow/flowDoc";
import { failureState, notPermittedState } from "./flow/flowFailure";
import { handleShortcut } from "./flow/flowShortcuts";
import { blockGroups } from "./flow/workflowBlocks";
import { loadCapabilities } from "./flow/workflowCapabilities";
import { workflowEdges, workflowNodes } from "./flow/workflowGraph";
import { insertAfter, newStep } from "./flow/workflowSteps";
import { triggerFromValue, triggerGroups } from "./flow/workflowTriggers";
import { useFlowDoc } from "./flow/useFlowDoc";

const props = defineProps({
	doctype: { type: String, default: FLOW_DOCTYPE },
	name: { type: String, default: null },
	query: { type: Object, default: () => ({}) },
});

const router = useRouter();
const flow = useFlowDoc(props.name, props.query);
const permits = useDocPermissions(FLOW_DOCTYPE);
const header = ref(null);
const selectedId = ref("");

const nodes = computed(() => workflowNodes(flow.doc, flow.errors));
const edges = computed(() => workflowEdges(flow.doc.actions));
// A new flow needs the create right; the insert checks again.
const checking = computed(() => !props.name && permits.loading.value);
const denied = computed(() => !props.name && !checking.value && !permits.holds("create"));
const failure = computed(() => (denied.value ? notPermittedState() : failureState(flow.failure)));

flow.load();
watch(
	() => props.name,
	(name) => name !== flow.current() && flow.load(name)
);
watch(() => flow.doc?.document_type, loadOffers, { immediate: true });

useUnloadGuard(() => flow.unsaved);
onBeforeRouteLeave(() => !flow.unsaved || confirmDiscard());
onBeforeRouteUpdate((to) => to.params.name === props.name || !flow.unsaved || confirmDiscard());
onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));

async function loadOffers(doctype) {
	try {
		await loadCapabilities(doctype);
	} catch {
		toast.error(__("The triggers and actions of {0} could not be loaded", [doctype]));
	}
}

function onKeydown(event) {
	handleShortcut(event, { save, undo: flow.undo, redo: flow.redo });
}

async function save() {
	if (!flow.doc) return;
	const wasNew = flow.isNew;
	if (!flow.doc.title?.trim()) header.value?.focusTitle();
	if (await flow.save()) {
		if (wasNew) router.replace(routeFor(FLOW_DOCTYPE, flow.doc.name));
	}
}

function pickStart(value) {
	Object.assign(flow.doc, triggerFromValue(value));
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
</script>
