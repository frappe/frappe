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
			@keydown.escape="cancel"
		>
			<!-- `ui.props` binds first so it cannot clobber `field` or `modelValue`; Vue merges
			     duplicate listeners, so `ui.on.change` and the close-on-commit both fire. -->
			<component
				:is="field.ui?.component ?? resolved"
				v-bind="field.ui?.props"
				:field="controlField"
				:modelValue="doc[field.fieldname]"
				@update:modelValue="(value: any) => edit(field.fieldname, value)"
				@change="(value: any) => onCommit(value)"
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
import {
	CommitKey,
	DocKey,
	NO_COMMIT,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/components/FormLayout/types";
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import { getFormatDefaults } from "@framework/ui/components/FormLayout/formatDefaults";
import { resolveFieldCurrency } from "@framework/ui/components/FormLayout/resolveCurrency";
import { displayValue, isSummaryField } from "./displayValue";

const props = defineProps<{ field: FieldNode }>();
const emit = defineEmits<{ expand: [field: FieldNode] }>();

const doc = inject(DocKey)!;
const update = inject(UpdateKey)!;
const commit = inject(CommitKey, NO_COMMIT);
const resolveField = inject(ResolveFieldKey)!;

function edit(fieldname: string, value: any) {
	update(fieldname, value);
	commit.pending(fieldname, value);
}

// A commit both closes the inline editor and fires the field's handler.
function onCommit(value: any) {
	editing.value = false;
	commit.commit(props.field.fieldname, value);
}

const editing = ref(false);
const cell = ref<HTMLElement | null>(null);
let opening: any;

// Every keystroke already wrote the draft, so a cancel has to put the opening value back.
function cancel() {
	update(props.field.fieldname, opening);
	editing.value = false;
}

const summary = computed(() => isSummaryField(props.field.fieldtype));
const interactive = computed(() => summary.value || !props.field.readOnly);
const resolved = computed(() => resolveField(props.field.fieldtype));

// The label already occupies its own column, so the control must not render a second one.
const controlField = computed(() => ({ ...props.field, label: undefined }));

const placeholder = computed(() =>
	interactive.value && !summary.value ? `Add ${props.field.label}...` : ""
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
	opening = doc.value[props.field.fieldname];
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
