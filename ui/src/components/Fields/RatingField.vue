<template>
	<Rating
		:modelValue="stars"
		:max="starCount"
		:step="0.5"
		:label="field.label"
		:description="field.description"
		:required="field.reqd"
		:disabled="field.readOnly"
		@update:modelValue="onUpdate"
	/>
</template>

<script setup lang="ts">
// Frappe persists a rating as a `0..1` fraction; the control works in star units
// (`0..max`), so this wrapper converts (`× starCount` in, `÷ starCount` out).
// `field.options` holds the star count (defaults to 5).
import { computed } from "vue";
import { Rating } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const starCount = computed(() => Number(props.field.options) || 5);

const stars = computed(() => (Number(props.modelValue) || 0) * starCount.value);

function onUpdate(starValue: number) {
	const fraction = starValue / starCount.value;
	emit("update:modelValue", fraction);
	emit("change", fraction);
}
</script>
