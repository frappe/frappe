<!-- The Automation Flow builder: the flow's header row over a canvas of its trigger and steps. -->
<template>
	<template v-if="flow.doc">
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
				:start-options="triggerGroups(flow.doc.document_type)"
				:block-options="blockGroups(flow.doc.document_type)"
				@select="selectedId = $event"
				@pick-start="pickStart"
				@add-node="addNode"
			/>
		</div>
	</template>
	<div v-else-if="flow.failure" class="m-auto flex flex-col items-center gap-3 px-8 text-center">
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
import { onBeforeRouteLeave, useRouter } from "vue-router";
import { Button, LoadingIndicator } from "frappe-ui";
import { __ } from "frappe/i18n";
import { AutomationCanvas } from "@framework/ui/AutomationCanvas";
import { routeFor, useUnloadGuard } from "@shell";
import FlowHeader from "./FlowHeader.vue";
import { confirmDiscard } from "./flow/confirmDiscard";
import { FLOW_DOCTYPE, stepById } from "./flow/flowDoc";
import { failureState } from "./flow/flowFailure";
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
});

const router = useRouter();
const flow = useFlowDoc(props.name);
const header = ref(null);
const selectedId = ref("");

const nodes = computed(() => workflowNodes(flow.doc, flow.errors));
const edges = computed(() => workflowEdges(flow.doc.actions));
const failure = computed(() => failureState(flow.failure));

flow.load();
watch(
	() => props.name,
	(name) => name !== flow.current() && flow.load(name)
);
watch(() => flow.doc?.document_type, loadCapabilities, { immediate: true });

useUnloadGuard(() => flow.unsaved);
onBeforeRouteLeave(() => !flow.unsaved || confirmDiscard());
onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));

function onKeydown(event) {
	handleShortcut(event, { save, undo: flow.undo, redo: flow.redo });
}

async function save() {
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
