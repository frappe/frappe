<script setup>
import SearchBox from "./SearchBox.vue";
import draggable from "vuedraggable";
import { ref, computed } from "vue";

let search_text = ref("");

function clone_field(field) {
	field.df.name = frappe.utils.get_random(8);
	return JSON.parse(JSON.stringify(field));
}

let fields = computed(() => {
	let fields = frappe.model.all_fieldtypes
		.filter(df => {
			if (in_list(["Tab Break", "Section Break", "Column Break", "Fold"], df)) {
				return false;
			}
			if (search_text.value) {
				if (df.toLowerCase().includes(search_text.value.toLowerCase())) {
					return true;
				}
				return false;
			} else {
				return true;
			}
		})
		.map(df => {
			let out = {
				df: {
					label: "",
					fieldname: "",
					fieldtype: df,
					options: "",
				},
				table_columns: [],
				new_field: true,
			};
			return out;
		});

	return [...fields];
});

</script>

<template>
	<SearchBox v-model="search_text" />
	<draggable
		class="fields-container"
		:list="fields"
		:group="{ name: 'fields', pull: 'clone', put: false }"
		:sort="false"
		:clone="clone_field"
		item-key="id"
	>
		<template #item="{ element }">
			<div class="field" :title="element.df.fieldtype">
				{{ element.df.fieldtype }}
			</div>
		</template>
	</draggable>
</template>

<style lang="scss" scoped>
.fields-container {
	display: grid;
	gap: 8px;
	padding: 8px;
	grid-template-columns: 1fr 1fr;

	.field {
		background-color: var(--bg-light-gray);
		border-radius: var(--border-radius);
		border: 1px dashed var(--gray-400);
		padding: 0.5rem 0.75rem;
		font-size: var(--text-sm);
		cursor: pointer;
	}
}
</style>
