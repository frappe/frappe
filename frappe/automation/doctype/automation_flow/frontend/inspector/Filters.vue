<template>
	<div class="space-y-2">
		<div v-if="label" class="flex items-center gap-1">
			<label class="block text-sm text-ink-gray-5">{{ label }}</label>
			<Tooltip v-if="info" :text="info">
				<Icon icon="lucide-info" class="size-3.5 text-ink-gray-5" />
			</Tooltip>
		</div>
		<ConditionBuilder
			v-if="tree.conditions.length"
			:key="doctype"
			:model-value="tree"
			:doctype="doctype"
			:max-depth="flat ? 0 : 2"
			bordered="all"
			@update:model-value="store"
		/>
		<!-- The builder's empty state is a box of its own; this is the card other builders show while empty. -->
		<div v-else class="flex w-full rounded-6 border border-outline-gray-2 p-3">
			<Dropdown v-if="!flat" v-slot="{ open }" :options="addOptions">
				<Button
					:label="__('Add Condition')"
					icon-left="lucide-plus"
					:icon-right="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
				/>
			</Dropdown>
			<Button
				v-else
				:label="__('Add Condition')"
				icon-left="lucide-plus"
				@click="addCondition"
			/>
		</div>
		<p v-if="flat && tree.conditions.length > 1" class="text-xs text-ink-gray-5">
			{{ __("A trigger runs only when these filters match.") }}
		</p>
	</div>
</template>

<script setup>
import { ref, watch } from "vue";
import { Button, Dropdown, Icon, Tooltip } from "frappe-ui";
import { __ } from "frappe/i18n";
import {
	ConditionBuilder,
	emptyTree,
	fromFrappeConditions,
	toFrappeConditions,
} from "@framework/ui/ConditionBuilder";

// The builder names its operators; frappe's filter grammar wants its own tokens.
const TOKENS = { equals: "=", "not equals": "!=" };

/**
 * The framework's condition builder, bound to the interleaved array the flow stores. The tree
 * lives here, not in the stored value: a row with no field yet is dropped on write, so a blank
 * row read back from the store would vanish as it was added.
 */
const props = defineProps({
	modelValue: { type: [String, Array], default: "" },
	doctype: { type: String, default: "" },
	label: { type: String, default: () => __("Filters") },
	// Hides the grouping controls. Conjunctions are still stored and honoured.
	flat: { type: Boolean, default: false },
	info: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

const tree = ref(fromFrappeConditions(read(props.modelValue)));
// What this last mirrored out, so an echo of it does not reload the tree.
let mirrored = serialize(tree.value);

const addOptions = [
	{ label: __("Add Condition"), onClick: () => addCondition() },
	{ label: __("Add Condition Group"), onClick: () => addGroup() },
];

// Selecting another step hands this the next condition, so reload the tree.
watch(
	() => props.modelValue,
	(value) => {
		const incoming = JSON.stringify(read(value));
		if (incoming === mirrored) return;
		tree.value = fromFrappeConditions(read(value));
		mirrored = incoming;
	}
);

function addCondition() {
	append({ fieldname: "", operator: "equals", value: "" });
}

function addGroup() {
	append(emptyTree());
}

function append(node) {
	store({ ...tree.value, conditions: [...tree.value.conditions, node] });
}

function store(next) {
	tree.value = next;
	mirrored = serialize(next);
	emit("update:modelValue", mirrored);
}

function serialize(next) {
	return JSON.stringify(toFrappeConditions(next).map(row));
}

function read(value) {
	if (Array.isArray(value)) return value;
	try {
		const parsed = JSON.parse(value || "[]");
		return Array.isArray(parsed) ? parsed : [];
	} catch {
		return [];
	}
}

function row(entry) {
	if (typeof entry === "string") return entry;
	if (Array.isArray(entry[0])) return entry.map(row);
	const [fieldname, operator, value] = entry;
	// "is not set" is "is" read the other way round, and "is" is all frappe knows.
	if (operator === "is not") return [fieldname, "is", value === "set" ? "not set" : "set"];
	return [fieldname, TOKENS[operator] || operator, value];
}
</script>

<style scoped>
/* The panel is ~310px wide: stack each row, as the app's other condition builders do. */
:deep([data-slot="condition-builder"]) {
	container-type: inline-size;
}

@container (max-width: 420px) {
	/* !important: the row and the leaf set their grids inline. */
	:deep([data-slot="condition-group"] li) {
		position: relative;
		grid-template-columns: minmax(0, 1fr) !important;
	}

	/* Field and operator share a line; the value takes the line under. */
	:deep([data-slot="condition-leaf"]) {
		grid-column: span 1 !important;
		grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr) !important;
	}

	:deep([data-slot="condition-value"]) {
		grid-column: 1 / -1;
	}

	/* The bracket joins side-by-side rows; stacked, it is a stray tick. */
	:deep([data-slot="condition-group"] li > :first-child > span) {
		display: none;
	}

	/* A group's card opens with its own "Where"; the row's copy is noise. */
	:deep([data-slot="condition-group"]
			li:first-child:has([data-slot="condition-group"])
			> :first-child) {
		display: none;
	}

	/* Stacked, the word leads the row and needs the gap the grid gave its columns. */
	:deep([data-slot="condition-group"] li > :first-child) {
		margin-bottom: 0.5rem;
	}

	:deep([data-slot="condition-group"] li > :first-child > div) {
		justify-content: flex-start;
	}

	/* The add button belongs to the rows above it. */
	:deep([data-slot="condition-group"]:has(> ul) > div) {
		margin-top: -0.5rem;
	}

	/* An empty group is all button: centre it. */
	:deep([data-slot="condition-group"]:not(:has(> ul)) > div) {
		justify-content: center;
	}

	:deep([data-slot="condition-field"] button) {
		width: 100%;
		max-width: 100%;
	}

	/* Lift the whole actions cell out of the flow, or it leaves a blank band under each row. */
	:deep(li:not(:has([data-slot="condition-group"])) > :nth-child(3)) {
		position: absolute;
		right: -0.25rem;
		top: -0.25rem;
	}

	/* A group's menu sits on its add-condition line, not beside a row's menu. */
	:deep(li:has([data-slot="condition-group"]) > :nth-child(3)) {
		position: absolute;
		right: 0.75rem;
		bottom: 0.75rem;
	}
}
</style>
