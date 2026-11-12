<template>
	<!-- A panel row has no edit state: the stars sit at x = 8 and a read-only row mutes them. -->
	<div
		v-if="panel"
		class="flex h-7 w-full items-center ps-2"
		:class="field.readOnly ? 'opacity-50' : ''"
	>
		<Rating
			v-bind="ratingProps"
			:aria-label="field.label"
			:aria-invalid="error?.length ? true : undefined"
			@update:modelValue="onUpdate"
		/>
	</div>
	<Rating
		v-else
		v-bind="ratingProps"
		:label="field.label"
		:description="field.description"
		:required="field.reqd"
		:error="error"
		@update:modelValue="onUpdate"
	>
		<template v-if="field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</Rating>
</template>

<script setup lang="ts">
// Frappe persists a rating as a `0..1` fraction; the control works in star units
// (`0..max`), so this wrapper converts (`× starCount` in, `÷ starCount` out).
// `field.options` holds the star count (defaults to 5).
import { computed } from "vue";
import { Rating } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const starCount = computed(() => Number(props.field.options) || 5);

const stars = computed(() => (Number(props.modelValue) || 0) * starCount.value);

const ratingProps = computed(() => ({
	modelValue: stars.value,
	max: starCount.value,
	step: 0.5,
	disabled: props.field.readOnly,
}));

function onUpdate(starValue: number) {
	const fraction = starValue / starCount.value;
	emit("update:modelValue", fraction);
	emit("change", fraction);
}
</script>
