<template>
	<Duration
		v-model="value"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
	/>
</template>

<script setup lang="ts">
// frappe-ui `Duration` — doc stores seconds (`number | null`), matching its
// `v-model`. `update:modelValue` fires on commit, so we re-emit `change` too.
import { computed } from "vue";
import { Duration } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const value = computed<number | null>({
	get: () => props.modelValue ?? null,
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});
</script>
