<template>
	<!-- A panel row has no edit state: the whole box toggles, the checkbox at x = 8. -->
	<div
		v-if="panel"
		class="flex h-7 w-full items-center ps-2"
		:class="field.readOnly ? 'cursor-default' : 'cursor-pointer'"
		@click="onBoxClick"
	>
		<Checkbox
			v-model="value"
			:aria-label="field.label"
			:aria-invalid="error?.length ? true : undefined"
			:disabled="field.readOnly"
		/>
	</div>
	<Checkbox
		v-else
		v-model="value"
		:label="field.label"
		:description="field.description"
		:required="field.reqd"
		:error="error"
		:disabled="field.readOnly"
	>
		<template v-if="field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</Checkbox>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Checkbox } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// The doc holds `0 | 1`, as the server stores it; the checkbox speaks boolean.
const value = computed<boolean>({
	get: () => Boolean(props.modelValue),
	// Toggling a checkbox is a commit: sync the value and fire the trigger.
	set: (v) => {
		const checked = v ? 1 : 0;
		emit("update:modelValue", checked);
		emit("change", checked);
	},
});

// The checkbox toggles itself; only a click on the rest of the box needs help.
function onBoxClick(event: MouseEvent) {
	if (props.field.readOnly || (event.target as HTMLElement).closest("input")) return;
	value.value = !value.value;
}
</script>
