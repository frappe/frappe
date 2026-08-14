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
			@update:modelValue="(value: any) => update(field.fieldname, value)"
			v-on="field.ui?.on ?? {}"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { DocKey, ResolveFieldKey, UpdateKey } from "./types";
import type { FieldNode } from "./types";

const props = defineProps<{ field: FieldNode }>();

const doc = inject(DocKey)!;
const update = inject(UpdateKey)!;
const resolveField = inject(ResolveFieldKey)!;

// `ui.component` swaps the control for this one node; otherwise resolve by fieldtype.
const resolved = computed(() => resolveField(props.field.fieldtype));
</script>
