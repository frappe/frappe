<template>
	<div class="space-y-2">
		<div class="flex items-center justify-between gap-2">
			<div class="flex items-center gap-1">
				<label class="block text-base text-ink-gray-5">{{ label }}</label>
				<Tooltip v-if="info" :text="info">
					<Icon icon="lucide-info" class="size-3.5 text-ink-gray-5" />
				</Tooltip>
			</div>
			<TabButtons v-model="mode" :options="modes" />
		</div>

		<WorkflowFilters
			v-if="mode === 'filters'"
			:model-value="filters"
			:doctype="doctype"
			:label="''"
			@update:model-value="setFilters"
		/>
		<CodeEditor
			v-else
			language="python"
			:variant="variant"
			:model-value="modelValue || ''"
			:placeholder="placeholder"
			style="--cm-max-height: 13.5rem"
			@update:model-value="$emit('update:modelValue', $event)"
		/>

		<p v-if="mode !== 'expression'" class="text-xs text-ink-gray-5">
			{{ __("All filters must match.") }}
		</p>
		<p v-else-if="canUseFilters" class="text-xs text-ink-gray-5">
			{{ __("Python, evaluated against doc, target and context.") }}
		</p>
		<p v-else class="text-xs text-ink-gray-5">
			{{ __("Not something filters can express. Edit it below.") }}
		</p>
	</div>
</template>

<script setup>
import { __ } from "frappe/i18n";
import WorkflowFilters from "./Filters.vue";
import { isFilterExpression, toExpression, toFilters } from "../flow/workflowConditions";
import { Icon, TabButtons, Tooltip } from "frappe-ui";
import { CodeEditor } from "frappe-ui/code-editor";
import { computed, ref, watch } from "vue";

const props = defineProps({
	modelValue: { type: String, default: "" },
	fields: { type: Array, default: () => [] },
	doctype: { type: String, default: "" },
	variant: { type: String, default: "subtle" },
	label: { type: String, default: () => __("Condition") },
	placeholder: { type: String, default: "" },
	info: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

const modes = computed(() => [
	{ label: __("Filters"), value: "filters", disabled: !canUseFilters.value },
	{ label: __("Expression"), value: "expression" },
]);

/** Start on whichever mode can actually show what is stored. */
const mode = ref(isFilterExpression(props.modelValue) ? "filters" : "expression");

const canUseFilters = computed(() => isFilterExpression(props.modelValue));
const filters = computed(() => toFilters(props.modelValue) || []);

// Selecting another step, or hand-editing past what filters can express, re-picks the mode.
watch(
	() => props.modelValue,
	() => {
		if (!canUseFilters.value) mode.value = "expression";
	}
);

function setFilters(value) {
	const rows = typeof value === "string" ? JSON.parse(value || "[]") : value;
	// The builder already loaded this DocType's fields; they decide which values stay unquoted.
	emit("update:modelValue", toExpression(rows, props.fields));
}
</script>
