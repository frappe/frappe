<template>
	<Combobox
		v-if="options.length"
		v-model="picked"
		:options="options"
		:placeholder="__('Search fields')"
		:aria-label="__('Insert a field')"
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

<script setup>
import { computed, nextTick, ref } from "vue";
import { Button, Combobox } from "frappe-ui";

const props = defineProps({
	fields: { type: Array, default: () => [] },
});

const emit = defineEmits(["insert"]);

// Params are templates, so a value can quote the record it acts on; a DocType with sixty fields needs search.
const options = computed(() =>
	props.fields
		.filter((field) => field.fieldname)
		.map((field) => ({
			label: field.label || field.fieldname,
			description: field.fieldname,
			value: field.fieldname,
		}))
);

// Cleared after each pick, or picking the same field twice in a row would not fire.
const picked = ref(null);

function insert(fieldname) {
	if (fieldname) emit("insert", `{{ doc.${fieldname} }}`);
	nextTick(() => (picked.value = null));
}
</script>
