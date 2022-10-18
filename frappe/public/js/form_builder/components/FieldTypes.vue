<script setup>
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
			if (
				in_list(["Tab Break", "Section Break", "Column Break", "Fold"], df)
			) {
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
	<div class="search-box">
		<input
			class="search-input form-control form-control-sm"
			type="text"
			:placeholder="__('Search fields')"
			v-model="search_text"
		/>
		<span class="search-icon">
			<svg class="icon icon-sm">
				<use href="#icon-search"></use>
			</svg>
		</span>
	</div>
	<draggable
		class="fields-container"
		:list="fields"
		:group="{ name: 'fields', pull: 'clone', put: false }"
		:sort="false"
		:clone="clone_field"
		item-key="id"
	>
		<template #item="{ element }">
			<div
				class="field"
				:title="element.df.fieldtype"
			>
				{{ element.df.fieldtype }}
			</div>
		</template>
	</draggable>
</template>

<style lang="scss" scoped>
.search-box {
	display: flex;
	position: relative;
	margin-bottom: 0.5rem;

	.search-input {
		padding-left: 30px;
	}

	.search-icon {
		position: absolute;
		margin-left: 8px;
		display: flex;
		align-items: center;
		height: 100%;
	}
}
.fields-container {
	max-height: calc(100vh - 240px);
	overflow-y: auto;

	.field {
		display: flex;
		justify-content: space-between;
		align-items: center;
		background-color: var(--bg-light-gray);
		border-radius: var(--border-radius);
		border: 1px dashed var(--gray-400);
		padding: 0.5rem 0.75rem;
		margin: 5px;
		margin-top: 0;
		font-size: var(--text-sm);
		cursor: pointer;

		&:not(:first-child) {
			margin-top: 0.5rem;
		}
	}
}
</style>
