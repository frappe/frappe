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
				:error="error"
				@update:modelValue="(value: any) => edit(field.fieldname, value)"
				@change="(value: any) => onCommit(value)"
				v-on="field.ui?.on ?? {}"
			/>
		</div>

		<div
			v-else
			class="group flex min-w-0 flex-wrap items-center gap-x-1.5 rounded px-1.5 py-1"
			:class="interactive ? 'cursor-pointer hover:bg-surface-gray-2' : ''"
			:data-fieldname="field.fieldname"
			@click="open"
		>
			<span
				class="min-w-0 flex-1 truncate text-base"
				:class="error ? 'text-ink-red-4' : display ? 'text-ink-gray-8' : 'text-ink-gray-4'"
			>
				{{ display || placeholder }}
			</span>
			<span
				v-if="summary"
				class="lucide-arrow-up-right ml-auto size-3.5 shrink-0 text-ink-gray-5"
				aria-hidden="true"
			/>
			<RecordAnchor
				v-else-if="record.href.value"
				:href="record.href.value"
				:aria-label="openLabel"
				:title="openLabel"
				class="lucide-arrow-up-right ml-auto size-3.5 shrink-0 text-ink-gray-5 opacity-0 hover:text-ink-gray-7 focus-visible:opacity-100 group-hover:opacity-100"
				@open="record.open"
			/>
			<span v-if="message" class="w-full truncate text-sm text-ink-red-4" :title="message">
				{{ message }}
			</span>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref, watch } from "vue";
import {
	CommitKey,
	DocKey,
	LinkTitlesKey,
	NO_COMMIT,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/FormLayout/types";
import { FieldErrorsKey, fieldErrorKey } from "@framework/ui/fields/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { RecordAnchor } from "@framework/ui/Link";
import { focusField, useRecordLink } from "@framework/ui/fields";
import { isSummaryField, useFieldDisplay } from "@framework/ui/FormLayout";
import { __ } from "@/i18n";
import { PanelContextKey } from "./context";

const props = defineProps<{ field: FieldNode }>();
const emit = defineEmits<{ expand: [field: FieldNode] }>();

const doc = inject(DocKey)!;
const update = inject(UpdateKey)!;
const commit = inject(CommitKey, NO_COMMIT);
const resolveField = inject(ResolveFieldKey)!;
const context = inject(PanelContextKey, null);
const titles = inject(LinkTitlesKey, null);
const displayField = useFieldDisplay();
const errors = inject(FieldErrorsKey, null);
const error = computed(() => errors?.value[fieldErrorKey(props.field.fieldname)]);
const message = computed(() => [error.value ?? []].flat().join(" "));

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

// A field that Details does not draw has nowhere to open, so its row edits in place.
const summary = computed(
	() =>
		isSummaryField(props.field.fieldtype) &&
		(context?.onDetails(props.field.fieldname) ?? true)
);
const interactive = computed(() => summary.value || !props.field.readOnly);
const resolved = computed(() => resolveField(props.field.fieldtype));

// The label already occupies its own column, so the control must not render a second one.
const controlField = computed(() => ({ ...props.field, label: undefined }));

const placeholder = computed(() =>
	interactive.value && !summary.value ? `Add ${props.field.label}...` : ""
);

const display = computed(() => displayField(props.field, doc.value));

const record = useRecordLink(linkedDoctype, () => doc.value[props.field.fieldname] || null);
const openLabel = computed(() => {
	const title = titles?.value[`${linkedDoctype()}::${doc.value[props.field.fieldname]}`];
	return __("Open {0}", [title ?? display.value]);
});

function linkedDoctype(): string {
	const { fieldtype, options } = props.field;
	if (fieldtype === "Link") return options ?? "";
	if (fieldtype === "Dynamic Link" && options) return doc.value[options] ?? "";
	return "";
}

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

watch(editing, async (on, _previous, onCleanup) => {
	if (!on) return;
	let stop = () => {};
	onCleanup(() => stop());
	await nextTick();
	if (cell.value) stop = focusField(cell.value);
});
</script>
