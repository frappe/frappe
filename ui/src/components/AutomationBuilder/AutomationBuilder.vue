<template>
	<div ref="root" class="flex h-full min-h-0 bg-surface-base p-2">
		<div
			class="automation-card flex min-w-0 flex-1 flex-col overflow-hidden rounded-6 bg-surface-gray-1 shadow-sm ring-1 ring-outline-gray-1"
		>
			<div
				class="flex h-14 shrink-0 items-center justify-between border-b border-outline-gray-2 px-4"
			>
				<div class="flex min-w-0 items-center gap-2">
					<Breadcrumbs class="automation-breadcrumbs" :items="breadcrumbs">
						<template #prefix>
							<WorkflowIcon class="mr-1.5 size-4 text-ink-gray-5" />
						</template>
					</Breadcrumbs>
					<span class="text-ink-gray-5 text-sm-semibold" aria-hidden="true">/</span>
					<div
						class="flex min-w-0 cursor-text items-center gap-1 rounded-4 pr-1.5 transition-colors hover:bg-surface-gray-2"
						@focus="selectTitle"
					>
						<div
							class="title-sizer font-semibold text-ink-gray-7 -mr-2.5"
							:data-value="doc.title || __('Untitled automation')"
						>
							<TextInput
								variant="ghost"
								:model-value="doc.title"
								:aria-label="__('Automation title')"
								:placeholder="__('Untitled automation')"
								@update:model-value="setTitle"
							/>
						</div>
					</div>
					<span class="-ml-1.5 select-none text-ink-red-5" aria-hidden="true">*</span>
					<span class="sr-only">{{ __("(required)") }}</span>
				</div>
				<div class="flex items-center gap-2">
					<Badge
						v-if="dirty"
						size="md"
						:label="__('Unsaved')"
						theme="amber"
						variant="subtle"
					>
						<template #prefix>
							<span class="size-1.5 rounded-full bg-current" aria-hidden="true" />
						</template>
					</Badge>

					<Button
						:label="__('Save')"
						variant="solid"
						:loading="saving"
						:disabled="!dirty"
						@click="saveAutomation"
					/>
					<Button
						icon="lucide-x"
						variant="ghost"
						:aria-label="__('Close')"
						@click="requestClose"
					/>
				</div>
			</div>
			<div
				class="flex shrink-0 items-center justify-between border-b border-outline-gray-2 px-4 py-2"
			>
				<TabButtons v-model="tab" :options="tabOptions" />
				<div class="flex items-center gap-2">
					<span class="text-sm text-ink-gray-6"> {{ __("Enabled") }} </span>
					<Switch
						size="sm"
						:model-value="Boolean(doc.enabled)"
						:disabled="!doc.trigger_type"
						@update:model-value="doc.enabled = $event ? 1 : 0"
					/>
				</div>
			</div>
			<div v-if="tab === 'test'" class="min-h-0 flex-1 p-4">
				<AutomationTrialRun v-if="canTest" :automation-name="doc.name" :doc="doc" />
				<p v-else class="text-sm text-ink-gray-5">
					{{ __("Save the flow before testing it.") }}
				</p>
			</div>
			<div v-else class="relative min-h-0 flex-1 outline-none" autofocus tabindex="0">
				<AutomationCanvas
					:nodes="canvasNodes"
					:edges="edges"
					:block-options="blocks"
					:start-options="triggers"
					:selected-id="selectedId"
					@select="selectNode"
					@add-node="addStep"
					@pick-start="pickTrigger"
				>
					<template #toolbar>
						<Button
							icon="lucide-undo-2"
							variant="ghost"
							:disabled="!canUndo"
							:aria-label="__('Undo')"
							@click="undo"
						/>
						<Button
							icon="lucide-redo-2"
							variant="ghost"
							:disabled="!canRedo"
							:aria-label="__('Redo')"
							@click="redo"
						/>
						<Button
							v-if="canDeleteSelected"
							icon="lucide-trash-2"
							variant="ghost"
							class="text-ink-red-5"
							:aria-label="
								selectedId === 'trigger' ? __('Remove trigger') : __('Remove step')
							"
							@click.stop="confirmSelectedRemoval"
						/>
					</template>
				</AutomationCanvas>
				<Button
					v-if="doc.trigger_type"
					class="absolute right-3 top-3 z-10 shadow-sm transition-transform active:scale-95"
					variant="subtle"
					:aria-label="inspectorOpen ? __('Close inspector') : __('Open inspector')"
					:aria-expanded="inspectorOpen"
					@click="inspectorOpen = !inspectorOpen"
				>
					<template #icon>
						<CollapseIcon
							class="size-4 transition-transform duration-200 ease-out"
							:class="{ 'rotate-180': inspectorOpen }"
						/>
					</template>
				</Button>
			</div>
		</div>
		<div
			class="min-h-0 shrink-0 overflow-hidden transition-[width,margin,opacity] duration-200 ease-out motion-reduce:transition-none"
			:class="showInspector ? 'ml-2 w-[340px]' : 'ml-0 w-0 opacity-0'"
			:aria-hidden="!showInspector"
			:inert="!showInspector"
		>
			<div
				class="automation-card h-full w-[340px] overflow-hidden rounded-6 bg-surface-base"
			>
				<AutomationInspector
					:doc="doc"
					:selected-step="selectedStep"
					:targets="targetsFor(selectedStep)"
					:loading="loading"
					@update="patchDoc"
				/>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { translate as __ } from "../../utils/translate";
import AutomationInspector from "./AutomationInspector.vue";
import AutomationTrialRun from "./AutomationTrialRun.vue";
import AutomationCanvas from "../AutomationCanvas/AutomationCanvas.vue";
import { useShortcuts } from "./useShortcuts";
import { useUndoHistory } from "./useUndoHistory";
import { blockGroups } from "./blocks";
import { aliasTargets, loadCapabilities } from "./capabilities";
import { workflowEdges, workflowNodes } from "./graph";
import { triggerFromValue, triggerGroups } from "./triggers";
import { firstBlockingRow, hasValues, triggerIssue } from "./validation";
import {
	adoptRowKeys,
	insertAfter,
	layoutSteps,
	newStep,
	nodeAtRow,
	removeStep,
	stepsBefore,
	toRows,
	toTree,
} from "./steps";
import {
	Badge,
	Breadcrumbs,
	Button,
	Switch,
	TabButtons,
	TextInput,
	call,
	dialog,
	toast,
} from "frappe-ui";
import WorkflowIcon from "~icons/lucide/workflow";
import CollapseIcon from "~icons/lucide/chevrons-left";
import { computed, reactive, ref, watch } from "vue";

const props = defineProps({
	/** The Automation Flow to edit; empty starts a new one. */
	automationName: { type: String, default: "" },
	/** The DocType a new flow starts on. */
	doctype: { type: String, default: "" },
	/** The breadcrumb that closes the builder. */
	parentLabel: { type: String, default: () => __("Automations") },
});

const emit = defineEmits(["close", "saved", "update:dirty"]);
const root = ref(null);

const loading = ref(false);
const saving = ref(false);
const tab = ref("editor");
const inspectorOpen = ref(false);
const selectedId = ref("trigger");
const errors = reactive({});
const doc = reactive(defaultDoc());
const savedSnapshot = ref("");

const tabOptions = [
	{ label: __("Editor"), value: "editor" },
	{ label: __("Test Run"), value: "test" },
];

const breadcrumbs = [
	{
		label: props.parentLabel,
		onClick: () => requestClose(),
	},
];

const placed = computed(() => layoutSteps(doc.actions));

const selectedStep = computed(() => {
	return placed.value.find((item) => item.node._id === selectedId.value)?.node || null;
});

const nodes = computed(() => workflowNodes(doc, errors));
/** While a block is inspected the rest of the flow steps back, as a trial run does. */
const canvasNodes = computed(() =>
	nodes.value.map((node) =>
		showInspector.value && !node.data.empty && node.id !== selectedId.value
			? { ...node, data: { ...node.data, dimmed: true } }
			: node
	)
);
const edges = computed(() => workflowEdges(doc.actions));
const blocks = computed(() => blockGroups(doc.document_type));
const triggers = computed(() => triggerGroups(doc.document_type));

const relationships = computed(() => parseJson(doc.relationships, []));

/** Every alias a step can target, outputs of steps the flow gained included. */
const flowTargets = computed(() =>
	aliasTargets(doc.document_type, relationships.value, toRows(doc.actions))
);
/** Kept mounted while hidden so the panel can slide out instead of vanishing. */
const showInspector = computed(() => tab.value === "editor" && inspectorOpen.value);
const canDeleteSelected = computed(() =>
	selectedId.value === "trigger" ? Boolean(doc.trigger_type) : Boolean(selectedStep.value)
);

const {
	canUndo,
	canRedo,
	undo,
	redo,
	flush: flushHistory,
	reset: resetHistory,
	absorb: absorbHistory,
} = useUndoHistory(doc, applySnapshot, {
	// The server owns these: restoring the `modified` a step back carried would make the next
	// save a stale write, which the server rejects.
	ignore: ["enabled", "name", "creation", "owner", "modified"],
});

useShortcuts(root, [
	{
		keys: ["Backspace", "Delete"],
		guard: () => tab.value === "editor" && canDeleteSelected.value,
		action: confirmSelectedRemoval,
	},
	{ match: isUndoKey, action: undo },
	{ match: isRedoKey, action: redo },
]);

/** Compared against the last loaded/saved state so closing can warn about unsaved edits. */
const dirty = computed(() => savedSnapshot.value !== JSON.stringify(payload()));

/** A trial runs the saved flow, so unsaved edits would not be what gets tested. */
const canTest = computed(() => Boolean(doc.name) && !dirty.value);

watch(flowTargets, loadTargetCapabilities, { immediate: true, deep: true });
watch(dirty, (value) => emit("update:dirty", value), { immediate: true });

loadAutomation();

function defaultDoc() {
	return {
		doctype: "Automation Flow",
		title: "",
		document_type: props.doctype,
		enabled: 0,
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
		run_as: "Automation User",
		automation_user: "",
		revalidate_on_run: 0,
		actions: [],
		stop_on_error: 1,
		throttle_per_minute: 0,
	};
}

async function loadAutomation() {
	if (!props.automationName) return markClean();
	loading.value = true;
	try {
		const saved = await call("frappe.client.get", {
			doctype: "Automation Flow",
			name: props.automationName,
		});
		Object.assign(doc, saved, {
			actions: toTree((saved.actions || []).map(normalizeRow)),
		});
	} finally {
		loading.value = false;
		markClean();
		resetHistory();
	}
}

function markClean() {
	savedSnapshot.value = JSON.stringify(payload());
}

/** Take the server's name, timestamps and step keys, so the next save is not a stale write. */
function adoptSaved(saved, submitted) {
	flushHistory();
	const metadata = {
		name: saved.name,
		creation: saved.creation,
		owner: saved.owner,
		modified: saved.modified,
	};
	Object.assign(doc, metadata);
	Object.assign(submitted, metadata);
	adoptSubmittedKeys(submitted.actions, saved.actions || []);
	savedSnapshot.value = JSON.stringify(payload(submitted));
	absorbHistory();
}

function adoptSubmittedKeys(actions, rows) {
	const before = new Map(layoutSteps(actions).map(({ node }) => [node._id, { ...node }]));
	adoptRowKeys(actions, rows);
	const submitted = new Map(layoutSteps(actions).map(({ node }) => [node._id, node]));
	for (const { node } of placed.value) {
		const saved = submitted.get(node._id);
		const previous = before.get(node._id);
		if (!saved) continue;
		if (node.step_key === previous.step_key) node.step_key = saved.step_key;
		if (node._outcomeKey === previous._outcomeKey) node._outcomeKey = saved._outcomeKey;
		node.idx = saved.idx;
	}
}

/** Closing warns first about unsaved edits, wherever the builder is shown. */
function requestClose() {
	if (!dirty.value) return emit("close");
	dialog.danger({
		title: __("Unsaved changes"),
		message: __("You have unsaved changes. Do you wish to exit?"),
		size: "sm",
		confirmLabel: __("Discard and exit"),
		cancelLabel: __("Keep editing"),
		onConfirm: ({ close }) => {
			close();
			emit("close");
		},
	});
}

function setTitle(title) {
	doc.title = title;
}

/** Focus lands on the inner input, so select from the wrapper the icon shares. */
function selectTitle(event) {
	if (event.target instanceof HTMLInputElement) event.target.select();
}

function normalizeRow(row) {
	return {
		...row,
		step_type: row.step_type || "Action",
		params: stringify(row.params),
		related_condition: stringify(row.related_condition, ""),
	};
}

function stringify(value, fallback = "{}") {
	if (!value) return fallback;
	return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function parseJson(value, fallback) {
	if (!value) return fallback;
	if (typeof value !== "string") return value;
	try {
		return JSON.parse(value);
	} catch {
		return fallback;
	}
}

/** Load capabilities for the trigger DocType and every alias a step can target. */
function loadTargetCapabilities() {
	flowTargets.value.forEach((target) => loadCapabilities(target.doctype));
}

function targetsFor(step) {
	if (!step) return [];
	return aliasTargets(doc.document_type, relationships.value, stepsBefore(doc.actions, step));
}

function addStep({ afterId, branch, value }) {
	const block = blockByValue(value);
	if (!block) return;
	const after = placed.value.find((item) => item.node._id === afterId)?.node;
	const created = newStep(block.values);
	if (!after) doc.actions.push(created);
	else if (branch) after.children[branch].push(created);
	else insertAfter(doc.actions, after, created);
	selectedId.value = created._id;
	inspectorOpen.value = true;
}

function blockByValue(value) {
	return blocks.value.flatMap((group) => group.options).find((option) => option.value === value);
}

/** The inspector reports its edits rather than writing into the document it is shown. */
function patchDoc(values) {
	Object.assign(doc, values);
}

/** Restoring replaces the whole document, so the canvas rebuilds from the snapshot. */
function applySnapshot(snapshot) {
	Object.assign(doc, snapshot);
	clearErrors();
	keepSelectionValid();
}

/** A step back can remove the selected step; the trigger is always there to fall back on. */
function keepSelectionValid() {
	if (selectedId.value === "trigger") return;
	if (placed.value.some((item) => item.node._id === selectedId.value)) return;
	selectedId.value = "trigger";
}

function isUndoKey(event) {
	return withModifier(event) && !event.shiftKey && isKey(event, "z");
}

function isRedoKey(event) {
	if (!withModifier(event)) return false;
	return isKey(event, "y") || (event.shiftKey && isKey(event, "z"));
}

function withModifier(event) {
	return event.metaKey || event.ctrlKey;
}

function isKey(event, key) {
	return event.key.toLowerCase() === key;
}

function selectNode(id) {
	selectedId.value = id;
	if (id !== "trigger" || doc.trigger_type) inspectorOpen.value = true;
}

function pickTrigger(trigger) {
	applyTrigger(trigger);
	selectedId.value = "trigger";
	inspectorOpen.value = true;
}

/** Event triggers store as a Custom Event; anything else clears the event it replaces. */
function applyTrigger(value) {
	Object.assign(doc, triggerFromValue(value));
}

function removeSelectedStep() {
	if (!selectedStep.value) return;
	if (!removeStep(doc.actions, selectedStep.value)) return;
	selectedId.value = "trigger";
}

function confirmSelectedRemoval() {
	if (!canDeleteSelected.value) return;
	const deletingTrigger = selectedId.value === "trigger";
	dialog.danger({
		title: deletingTrigger ? __("Delete trigger") : __("Delete step"),
		size: "sm",
		message: deleteMessage(deletingTrigger),
		confirmLabel: __("Delete"),
		cancelLabel: __("Cancel"),
		onConfirm: ({ close }) => {
			if (deletingTrigger) resetTrigger();
			else removeSelectedStep();
			close();
		},
	});
}

function deleteMessage(deletingTrigger) {
	return deletingTrigger
		? __("Are you sure you want to delete the trigger and all workflow steps?")
		: __("Are you sure you want to delete this step?");
}

function resetTrigger() {
	Object.assign(doc, emptyTriggerState());
	selectedId.value = "trigger";
	inspectorOpen.value = false;
}

function emptyTriggerState() {
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
		actions: [],
	};
}

async function saveAutomation() {
	if (saving.value) return;
	flushHistory();
	saving.value = true;
	clearErrors();
	try {
		validateBeforeSave();
		const submitted = JSON.parse(JSON.stringify(doc));
		const method = doc.name ? "frappe.client.save" : "frappe.client.insert";
		const saved = await call(method, { doc: payload(submitted) });
		adoptSaved(saved, submitted);
		toast.success(__("Automation saved"));
		emit("saved", saved);
	} catch (error) {
		toast.error(attachError(error));
	} finally {
		saving.value = false;
	}
}

function validateBeforeSave() {
	const trigger = triggerIssue(doc);
	if (trigger) throw new Error(trigger);
	const blocking = firstBlockingRow(doc.actions);
	if (!blocking) return;
	attachRowError(blocking.row.idx, blocking.issue);
	throw new Error(blocking.issue);
}

function payload(source = doc) {
	return {
		...source,
		title: source.title || __("Untitled automation"),
		filters: normalizedJsonString(source.filters, []),
		relationships: JSON.stringify(normalizedRelationships(source)),
		actions: toRows(source.actions).map(rowPayload),
	};
}

function normalizedRelationships(source) {
	const value = parseJson(source.relationships, []);
	return Array.isArray(value) ? value : [];
}

function normalizedJsonString(value, fallback) {
	return JSON.stringify(parseJson(value, fallback));
}

function rowPayload(row) {
	return {
		...row,
		doctype: "Automation Action",
		params: JSON.stringify(normalizedParams(row)),
		related_condition: normalizedRelatedCondition(row.related_condition),
	};
}

function normalizedParams(row) {
	const params = parseJson(row.params, {});
	if (row.action_type !== "SetFieldValue") return params;
	if (!hasValues(params.values)) delete params.values;
	return params;
}

function normalizedRelatedCondition(value) {
	const condition = parseJson(value, null);
	if (!condition || Array.isArray(condition) || !condition.relationship) return null;
	return JSON.stringify(condition);
}

function clearErrors() {
	Object.keys(errors).forEach((key) => delete errors[key]);
}

/** Server errors read "Row 3: ..." - that points the error at its node, and the node being
    marked is what tells the user where it is, so the prefix leaves the message. */
function attachError(error) {
	const raw = errorMessage(error);
	const match = raw.match(/^Row (\d+):\s*/);
	const message = match ? raw.slice(match[0].length) : raw;
	if (match) attachRowError(Number(match[1]), message);
	else if (selectedStep.value) errors[selectedStep.value._id] = [{ message }];
	return message;
}

function attachRowError(rowIndex, message) {
	const node = nodeAtRow(doc.actions, rowIndex);
	if (!node) return;
	errors[node._id] = [{ message }];
	selectedId.value = node._id;
}

function errorMessage(error) {
	const messages = error?.messages || error?._server_messages;
	if (Array.isArray(messages) && messages.length) return cleanMessage(messages[0]);
	return cleanMessage(error?.message || error);
}

function cleanMessage(message) {
	try {
		return JSON.parse(message).message || String(message);
	} catch {
		return String(message || __("Could not save automation"));
	}
}
</script>

<style scoped>
/* Both panes rise into place when the builder opens. */
.automation-card {
	animation: card-in 220ms ease-out both;
}

@keyframes card-in {
	from {
		opacity: 0;
		transform: translateY(6px) scale(0.995);
	}
}

@media (prefers-reduced-motion: reduce) {
	.automation-card {
		animation: none;
	}
}

/* An invisible mirror of the text sets the track width, so the field is only
   ever as wide as its content until it hits the cap and truncates. */
.title-sizer {
	display: inline-grid;
	min-width: 0;
	max-width: min(20rem, 40vw);
}

.automation-breadcrumbs :deep(a),
.automation-breadcrumbs :deep(button) {
	@apply text-sm-medium;
}

.title-sizer::after,
.title-sizer > * {
	grid-area: 1 / 1;
	min-width: 0;
}

/* Same font and padding as TextInput's sm field so the mirror measures exactly the text. */
.title-sizer::after {
	@apply text-base;
	content: attr(data-value);
	visibility: hidden;
	white-space: pre;
	padding: 0 0.5rem;
}

/* Zero intrinsic width so only the mirror sizes the track; the input then fills it. */
.title-sizer :deep(input) {
	width: 0;
	min-width: 100%;
	cursor: text;
	background: transparent;
	text-overflow: ellipsis;
}

.title-sizer :deep(input::selection) {
	background: var(--surface-gray-3, #e2e8f0);
}
</style>
