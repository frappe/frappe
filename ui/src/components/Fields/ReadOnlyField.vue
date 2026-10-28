<template>
	<ReadValue
		:text="text"
		:label="field.label"
		:description="field.description"
		:required="field.reqd"
		:error="error"
	>
		<template v-if="address?.kind === 'mail'" #default>
			<a
				:href="address.href"
				data-slot="mail-link"
				class="text-ink-gray-8 underline-offset-2 hover:underline"
				>{{ text }}</a
			>
		</template>
		<template v-else-if="address?.kind === 'web'" #default>
			{{ text }}
			<DataOpenLink :address="address" class="inline-grid align-middle" />
		</template>
	</ReadValue>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import ReadValue from "./ReadValue.vue";
import DataOpenLink from "./DataOpenLink.vue";
import { dataHref } from "./dataOptions";
import { DocKey, ParentDocKey } from "./types";
import { NUMBER_FIELDTYPES } from "../FormLayout/formatNumber";
import { useFieldDisplay } from "../FormLayout/useFieldDisplay";
import type { FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();

const doc = inject(DocKey, null);
const parentDoc = inject(ParentDocKey, null);
const display = useFieldDisplay();

const text = computed(() => {
	const { field, modelValue } = props;
	const unset = modelValue == null || modelValue === "";
	const value = unset && NUMBER_FIELDTYPES.includes(field.fieldtype) ? 0 : modelValue;
	return display(field, value, {
		doc: doc?.value,
		row: props.row,
		parentDoc: parentDoc?.value,
	});
});

const address = computed(() => dataHref(props.field, props.modelValue));
</script>
