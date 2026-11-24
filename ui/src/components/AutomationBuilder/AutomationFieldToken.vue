<template>
	<Combobox
		v-if="options.length"
		v-model="picked"
		:options="options"
		:placeholder="__('Search fields')"
		@update:model-value="insert"
	>
		<template #trigger>
			<Button
				variant="ghost"
				size="sm"
				icon-left="lucide-braces"
				:label="__('Insert field')"
			/>
		</template>
	</Combobox>
</template>

<script setup lang="ts">
import { translate as __ } from "../../utils/translate";
import { Button, Combobox } from "frappe-ui";
import { computed, nextTick, ref } from "vue";

const props = defineProps({
	fields: { type: Array, default: () => [] },
});

const emit = defineEmits(["insert"]);

/**
 * Params are rendered as templates, so a value can quote the record it acts on. Offering the
 * fields is the difference between "type {{ doc.first_name }}" and picking "First Name" -
 * and searchable, because a document type with sixty fields is not a list you scroll.
 */
const options = computed(() =>
	props.fields
		.filter((field) => field.fieldname)
		.map((field) => ({
			label: field.label || field.fieldname,
			description: field.fieldname,
			value: field.fieldname,
		}))
);

// cleared after each pick, or picking the same field twice in a row would not fire
const picked = ref(null);

function insert(fieldname) {
	if (fieldname) emit("insert", `{{ doc.${fieldname} }}`);
	nextTick(() => (picked.value = null));
}
</script>
