<template>
	<Link
		v-model="value"
		:doctype="field.options ?? ''"
		:filters="field.filters"
		:title="title"
		:idLabels="isName"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:error="error"
		:disabled="field.readOnly"
	>
		<!-- Forward any slots (e.g. a #prefix affordance) on to the Link control. -->
		<template v-for="(_, name) in $slots" #[name]="slotProps" :key="name">
			<slot :name="name" v-bind="slotProps" />
		</template>
	</Link>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Link } from "../Link";
import { LinkTitlesKey } from "./types";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const titles = inject(LinkTitlesKey, null);

// `name` links to its own doctype and its value is the ID, so it shows the ID, not
// the title: the picked option then reads the same as the stored filter.
const isName = computed(() => props.field.fieldname === "name");

const title = computed(() =>
	props.modelValue && !isName.value
		? titles?.value[`${props.field.options}::${props.modelValue}`]
		: undefined
);

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	// A selection is a commit for a picker: sync the value and fire the trigger.
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});
</script>
