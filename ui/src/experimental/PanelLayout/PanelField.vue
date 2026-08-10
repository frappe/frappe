<!-- One panel row: the label in a fixed column, the value in the flexible one. -->
<template>
	<div class="grid grid-cols-[130px_1fr] items-center gap-2">
		<span class="truncate text-base text-ink-gray-5" :title="field.label">
			{{ field.label }}
		</span>

		<div
			v-if="editing"
			ref="cell"
			class="field min-w-0"
			:data-fieldname="field.fieldname"
			@focusout="onFocusout"
			@keydown.escape="editing = false"
		>
			<component
				:is="field.ui?.component ?? resolved"
				:field="controlField"
				:modelValue="doc[field.fieldname]"
				@update:modelValue="(value: any) => update(field.fieldname, value)"
				@change="editing = false"
				v-bind="field.ui?.props"
				v-on="field.ui?.on ?? {}"
			/>
		</div>

		<div
			v-else
			class="flex min-w-0 items-center gap-1.5 rounded px-1.5 py-1"
			:class="interactive ? 'cursor-pointer hover:bg-surface-gray-2' : ''"
			:data-fieldname="field.fieldname"
			@click="open"
		>
			<span
				class="truncate text-base"
				:class="display ? 'text-ink-gray-8' : 'text-ink-gray-4'"
			>
				{{ display || placeholder }}
			</span>
			<span
				v-if="summary"
				class="lucide-arrow-up-right ml-auto size-3.5 shrink-0 text-ink-gray-5"
				aria-hidden="true"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref, watch } from "vue";
import { DocKey, ResolveFieldKey, UpdateKey } from "../../components/FormLayout/types";
import type { FieldNode } from "../../components/FormLayout/types";
import { getFormatDefaults } from "../../components/FormLayout/formatDefaults";
import { resolveFieldCurrency } from "../../components/FormLayout/resolveCurrency";
import { displayValue, isSummaryField } from "./displayValue";

const props = defineProps<{ field: FieldNode }>();
const emit = defineEmits<{ expand: [field: FieldNode] }>();

const doc = inject(DocKey)!;
const update = inject(UpdateKey)!;
const resolveField = inject(ResolveFieldKey)!;

const editing = ref(false);
const cell = ref<HTMLElement | null>(null);

const summary = computed(() => isSummaryField(props.field.fieldtype));
const interactive = computed(() => summary.value || !props.field.readOnly);
const resolved = computed(() => resolveField(props.field.fieldtype));

// The label already occupies its own column, so the control must not render a second one.
const controlField = computed(() => ({ ...props.field, label: undefined }));

const placeholder = computed(() =>
	interactive.value && !summary.value ? `Add ${props.field.label}...` : "",
);

const display = computed(() => {
	const defaults = getFormatDefaults();
	return displayValue(doc.value[props.field.fieldname], props.field, {
		precision: props.field.precision,
		currency:
			props.field.fieldtype === "Currency"
				? resolveFieldCurrency(props.field.options, {
						doc: doc.value,
						defaultCurrency: defaults.currency,
					})
				: undefined,
		numberFormat: defaults.number_format,
		roundingMethod: defaults.rounding_method,
	});
});

function open() {
	if (summary.value) return emit("expand", props.field);
	if (props.field.readOnly) return;
	editing.value = true;
}

// A picker's popover is portalled out of the cell, so focus landing outside the
// document body's flow is not the user leaving the field.
function onFocusout(event: FocusEvent) {
	const next = event.relatedTarget as HTMLElement | null;
	if (!next) return;
	if (cell.value?.contains(next)) return;
	if (next.closest('[role="dialog"],[role="listbox"],[role="menu"]')) return;
	editing.value = false;
}

watch(editing, async (on) => {
	if (!on) return;
	await nextTick();
	cell.value?.querySelector<HTMLElement>("input, textarea, select, button")?.focus();
});
</script>
