<template>
	<div class="field" :data-fieldname="field.fieldname" :data-fieldtype="field.fieldtype">
		<component
			:is="resolved"
			:field="field"
			:modelValue="doc[field.fieldname]"
			@update:modelValue="(value: any) => update(field.fieldname, value)"
			@change="(value: any) => commit(field.fieldname, value)"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { CommitKey, DocKey, ResolveFieldKey, UpdateKey } from "./types";
import type { FieldMeta } from "./types";

const props = defineProps<{ field: FieldMeta }>();

const doc = inject(DocKey)!;
const update = inject(UpdateKey)!;
const commit = inject(CommitKey)!;
const resolveField = inject(ResolveFieldKey)!;

const resolved = computed(() => resolveField(props.field.fieldtype));
</script>
