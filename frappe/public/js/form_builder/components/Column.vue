<script setup>
import draggable from "vuedraggable";
import Field from "./Field.vue";
import { ref } from "vue";
import { useStore } from "../store";

let props = defineProps(["section", "column"]);
let store = useStore();

let hovered = ref(false);

function add_column() {
	// insert new column after the current column
	let index = props.section.columns.indexOf(props.column);
	props.section.columns.splice(index + 1, 0, {
		df: store.get_df("Column Break", "column_break_" + frappe.utils.get_random(4)),
		fields: []
	});
}

function remove_column() {
	if (store.is_customize_form && store.is_custom(props.column) == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	}

	// move all fields to previous column
	let index = props.section.columns.indexOf(props.column);

	if (index > 0) {
		let prev_column = props.section.columns[index - 1];
		prev_column.fields = prev_column.fields.concat(props.column.fields);

		// remove column
		props.section.columns.splice(index, 1);
	}
}
</script>

<template>
	<div
		:class="[
			'column',
			hovered ? 'hovered' : '',
			store.selected(column.df.name) ? 'selected' : ''
		]"
		:title="column.df.fieldname"
		@click.stop="store.selected_field = column.df"
		@mouseover.stop="hovered = true"
		@mouseout.stop="hovered = false"
	>
		<div class="column-actions hidden" :hidden="store.read_only">
			<button class="btn btn-xs btn-icon" :title="__('Add Column')" @click="add_column">
				<div v-html="frappe.utils.icon('add', 'sm')"></div>
			</button>
			<button
				class="btn btn-xs btn-icon"
				:title="__('Remove Column')"
				@click="remove_column"
			>
				<div v-html="frappe.utils.icon('close', 'sm')"></div>
			</button>
		</div>
		<draggable
			class="column-container"
			:style="{
				backgroundColor: column.fields.length ? null : 'var(--gray-50)'
			}"
			v-model="column.fields"
			group="fields"
			filter="[data-is-custom='0']"
			:animation="150"
			item-key="id"
			:disabled="store.read_only"
		>
			<template #item="{ element }">
				<Field
					:column="column"
					:field="element"
					:data-is-custom="store.is_custom(element)"
				/>
			</template>
		</draggable>
	</div>
</template>

<style lang="scss" scoped>
.column {
	display: flex;
	flex-direction: column;
	width: 100%;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius);
	border: 1px solid var(--gray-400);
	padding: 0.5rem;
	margin-left: 4px;
	margin-right: 4px;

	&.hovered,
	&.selected {
		border-color: var(--primary);
		.btn.btn-icon {
			opacity: 1 !important;
		}
	}

	&.selected {
		.column-actions {
			display: flex !important;
		}

		.column-container {
			height: 80%;
		}
	}

	&:first-child {
		margin-left: 0px;
	}

	&:last-child {
		margin-right: 0px;
	}

	.column-container {
		flex: 1;
		min-height: 2rem;
		border-radius: var(--border-radius);
	}

	.column-actions {
		display: flex;
		justify-content: flex-end;
		padding-bottom: 0.5rem;

		.btn.btn-icon {
			padding: 2px;
			box-shadow: none;
			opacity: 0;

			&:hover {
				opacity: 1;
				background-color: var(--fg-color);
			}
		}
	}
}
</style>
