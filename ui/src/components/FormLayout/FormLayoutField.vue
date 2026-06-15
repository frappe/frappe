<template>
	<div class="field" :data-fieldname="field.fieldname" :data-fieldtype="field.fieldtype">
		<component
			:is="field.ui?.component ?? resolved"
			:field="field"
			:modelValue="doc[field.fieldname]"
			@update:modelValue="(value: any) => update(field.fieldname, value)"
			v-bind="field.ui?.props"
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
