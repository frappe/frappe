<template>
	<Duration
		v-model="value"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		v-bind="{ ...frame, ...durationUnits(field) }"
	>
		<template v-if="!panel && field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</Duration>
</template>

<script setup lang="ts">
// frappe-ui `Duration` — doc stores seconds (`number | null`), matching its
// `v-model`. `update:modelValue` fires on commit, so we re-emit `change` too.
import { computed } from "vue";
import { Duration } from "frappe-ui";
import { durationUnits } from "./durationUnits";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";
import { useInputFrame } from "./inputFrame";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
const frame = useInputFrame(props);

const value = computed<number | null>({
	get: () => props.modelValue ?? null,
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});
</script>
