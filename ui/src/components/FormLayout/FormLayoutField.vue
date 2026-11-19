<template>
	<div
		ref="root"
		class="field"
		:data-fieldname="field.fieldname"
		:data-fieldtype="field.fieldtype"
		:autofocus="autofocusField === field.fieldname || undefined"
	>
		<!-- `ui.props` binds FIRST so it cannot clobber `field` or `modelValue`:
		     it is presentation, not a way to re-point the control at another
		     field. Listeners are unaffected by the order — Vue merges duplicate
		     handlers into an array, so `ui.on.change` and the layout's own
		     `update:modelValue` both fire. -->
		<component
			:is="control"
			v-bind="{ ...field.ui?.props, ...scriptPage }"
			:field="field"
			:modelValue="doc[field.fieldname]"
			:error="error"
			@update:modelValue="(value: any) => edit(field.fieldname, value)"
			@change="(value: any) => onCommit(value)"
			v-on="field.ui?.on ?? {}"
		/>
		<FieldLabelAfter v-if="$slots['label-after']" :host="label">
			<slot name="label-after" />
		</FieldLabelAfter>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import {
	AutofocusKey,
	CommitKey,
	ControlPageKey,
	DocKey,
	NO_COMMIT,
	ResolveFieldKey,
	UpdateKey,
} from "./types";
import { holdsChildRows } from "../Fields/rowIdentity";
import { drawsReadValue } from "../Fields/readView";
import ReadOnlyField from "../Fields/ReadOnlyField.vue";
import { FieldLabelAfter } from "./FieldLabelAfter";
import { FieldErrorsKey, fieldErrorKey } from "../Fields/types";
import type { FieldNode } from "./types";

const props = defineProps<{ field: FieldNode }>();
const slots = defineSlots<{ "label-after"?: () => unknown }>();

const doc = inject(DocKey)!;
const update = inject(UpdateKey)!;
const commit = inject(CommitKey, NO_COMMIT);
const resolveField = inject(ResolveFieldKey)!;
const autofocusField = inject(AutofocusKey, null);
const errors = inject(FieldErrorsKey, null);
const page = inject(ControlPageKey, null);
// Only a script's own control gets `page`; the stock ones would carry it as a stray attribute.
const scriptPage = computed(() =>
	props.field.ui?.component && page?.value ? { page: page.value } : {}
);
const error = computed(() => errors?.value[fieldErrorKey(props.field.fieldname)]);

// A host's marks sit inside the control's own label, after its last word, and follow it as the control swaps.
const root = ref<HTMLElement | null>(null);
const label = shallowRef<Element | null>(null);
let watcher: MutationObserver | null = null;
onMounted(() => {
	if (!slots["label-after"]) return;
	const find = () => (label.value = root.value!.querySelector('[data-slot="label"]'));
	find();
	watcher = new MutationObserver(find);
	watcher.observe(root.value!, { childList: true, subtree: true });
});
onBeforeUnmount(() => watcher?.disconnect());

// A child table commits through its rows, never under its own fieldname, which
// ticket 45 retired as a handler key.
const commits = computed(() => !holdsChildRows(props.field.fieldtype));

// The live write, plus a note that a commit is owed: a save with focus still in
// the input has to fire the handler before `beforeSave` sees a stale value.
function edit(fieldname: string, value: any) {
	update(fieldname, value);
	if (commits.value) commit.pending(fieldname, value);
}

function onCommit(value: any) {
	if (commits.value) commit.commit(props.field.fieldname, value);
}

// `ui.component` swaps the control for this one node; otherwise resolve by fieldtype.
const control = computed(() => {
	if (drawsReadValue(props.field)) return ReadOnlyField;
	return props.field.ui?.component ?? resolveField(props.field.fieldtype);
});
</script>
