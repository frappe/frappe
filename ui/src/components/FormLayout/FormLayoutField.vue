<template>
	<div class="field" :data-fieldname="field.fieldname" :data-fieldtype="field.fieldtype">
		<!-- `ui.props` binds FIRST so it cannot clobber `field` or `modelValue`:
		     it is presentation, not a way to re-point the control at another
		     field. Listeners are unaffected by the order — Vue merges duplicate
		     handlers into an array, so `ui.on.change` and the layout's own
		     `update:modelValue` both fire. -->
		<component
			:is="field.ui?.component ?? resolved"
			v-bind="field.ui?.props"
			:field="field"
			:modelValue="doc[field.fieldname]"
			@update:modelValue="(value: any) => edit(field.fieldname, value)"
			@change="(value: any) => onCommit(value)"
			v-on="field.ui?.on ?? {}"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { CommitKey, DocKey, NO_COMMIT, ResolveFieldKey, UpdateKey } from "./types";
import { holdsChildRows } from "../Fields/rowIdentity";
import type { FieldNode } from "./types";

const props = defineProps<{ field: FieldNode }>();

const doc = inject(DocKey)!;
const update = inject(UpdateKey)!;
const commit = inject(CommitKey, NO_COMMIT);
const resolveField = inject(ResolveFieldKey)!;

// A child table commits through its rows, never under its own fieldname, which
// ticket 45 retired as a handler key.
const commits = computed(() => !holdsChildRows(props.field.fieldtype));

// The live write, plus a note that a commit is owed: a save with focus still in
// the input has to fire the handler before `before_save` sees a stale value.
function edit(fieldname: string, value: any) {
	update(fieldname, value);
	if (commits.value) commit.pending(fieldname, value);
}

function onCommit(value: any) {
	if (commits.value) commit.commit(props.field.fieldname, value);
}

// `ui.component` swaps the control for this one node; otherwise resolve by fieldtype.
const resolved = computed(() => resolveField(props.field.fieldtype));
</script>
