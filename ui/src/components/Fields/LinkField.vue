<template>
	<Link
		v-model="value"
		:doctype="field.options ?? ''"
		:filters="field.filters"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
	>
		<!-- Forward any slots (e.g. a #prefix affordance) on to the Link control. -->
		<template v-for="(_, name) in $slots" #[name]="slotProps" :key="name">
			<slot :name="name" v-bind="slotProps" />
		</template>
	</Link>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Link } from "../Link";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	// A selection is a commit for a picker: sync the value and fire the trigger.
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});
</script>
