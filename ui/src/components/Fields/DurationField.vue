<template>
	<Duration
		v-model="value"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		v-bind="{ ...frame, ...durationUnits(field) }"
		@focusin="onFocusin"
	>
		<template v-if="!panel && field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</Duration>
</template>

<script setup lang="ts">
// frappe-ui `Duration` — doc stores seconds (`number | null`), matching its
// `v-model`. `update:modelValue` fires on commit, so we re-emit `change` too.
import { computed, nextTick } from "vue";
import { Duration } from "frappe-ui";
import { durationUnits } from "./durationUnits";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";
import { useInputFrame } from "./inputFrame";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
const frame = useInputFrame(props);

// Duration selects its text a tick after focus; a panel row opens with the caret at the end instead.
function onFocusin(event: FocusEvent) {
	const input = event.target;
	if (!props.panel || !(input instanceof HTMLInputElement)) return;
	nextTick(() => input.setSelectionRange(input.value.length, input.value.length));
}

const value = computed<number | null>({
	get: () => props.modelValue ?? null,
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});
</script>
