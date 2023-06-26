<script setup>
import draggable from "vuedraggable";
import Field from "./Field.vue";
import EditableInput from "./EditableInput.vue";
import { ref } from "vue";
import { useStore } from "../store";
import { move_children_to_parent, confirm_dialog } from "../utils";

const props = defineProps(["section", "column"]);
let store = useStore();

let hovered = ref(false);

function add_column() {
	// insert new column after the current column
	let index = props.section.columns.indexOf(props.column);
	props.section.columns.splice(index + 1, 0, {
		df: store.get_df("Column Break"),
		fields: [],
	});
}

function remove_column() {
	if (store.is_customize_form && props.column.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	} else if (props.column.fields.length == 0 || store.has_standard_field(props.column)) {
		delete_column();
	} else {
		confirm_dialog(
			__("Delete Column", null, "Title of confirmation dialog"),
			__("Are you sure you want to delete the column? All the fields in the column will be moved to the previous column.", null, "Confirmation dialog message"),
			() => delete_column(),
			__("Delete column", null, "Button text"),
			() => delete_column(true),
			__("Delete entire column with fields", null, "Button text")
		);
	}
}

function delete_column(with_children) {
	// move all fields to previous column
	let columns = props.section.columns;
	let index = columns.indexOf(props.column);

	if (with_children && index == 0 && columns.length == 1) {
		if (props.column.fields.length == 0) {
			frappe.msgprint(__("Section must have at least one column"));
			throw "section must have at least one column";
		}

		columns.unshift({
			df: store.get_df("Column Break"),
			fields: [],
			is_first: true,
		});
		index++;
	}

	if (!with_children) {
		if (index > 0) {
			let prev_column = columns[index - 1];
			prev_column.fields = [...prev_column.fields, ...props.column.fields];
		} else {
			if (props.column.fields.length == 0) {
				// set next column as first column
				let next_column = columns[index + 1];
				if (next_column) {
					next_column.is_first = true;
				} else {
					frappe.msgprint(__("Section must have at least one column"));
					throw "section must have at least one column";
				}
			} else {
				// create a new column if current column has fields and push fields to it
				columns.unshift({
					df: store.get_df("Column Break"),
					fields: props.column.fields,
					is_first: true,
				});
				index++;
			}
		}
	}

	// remove column
	columns.splice(index, 1);
	store.form.selected_field = null;
}

function move_columns_to_section() {
	move_children_to_parent(props, "section", "column", store.current_tab);
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
		@click.stop="store.form.selected_field = column.df"
		@mouseover.stop="hovered = true"
		@mouseout.stop="hovered = false"
	>
		<div
			:class="[
				'column-header',
				column.df.label ? 'has-label' : '',
			]"
			:hidden="!column.df.label && store.read_only"
		>
			<div class="column-label">
				<EditableInput
					:text="column.df.label"
					:placeholder="__('Column Title')"
					v-model="column.df.label"
				/>
			</div>
			<div class="column-actions">
				<button
					v-if="section.columns.indexOf(column)"
					class="btn btn-xs btn-icon"
					:title="__('Move the current column & the following columns to a new section')"
					@click="move_columns_to_section"
				>
					<div v-html="frappe.utils.icon('move', 'sm')"></div>
				</button>
				<button class="btn btn-xs btn-icon" :title="__('Add Column')" @click="add_column">
					<div v-html="frappe.utils.icon('add', 'sm')"></div>
				</button>
				<button
					class="btn btn-xs btn-icon"
					:title="__('Remove Column')"
					@click.stop="remove_column"
				>
					<div v-html="frappe.utils.icon('remove', 'sm')"></div>
				</button>
			</div>
		</div>
		<div v-if="column.df.description" class="column-description">
			{{ column.df.description }}
		</div>
		<draggable
			class="column-container"
			:style="{ backgroundColor: column.fields.length ? '' : 'var(--field-placeholder-color)' }"
			v-model="column.fields"
			group="fields"
			:animation="200"
			:easing="store.get_animation"
			item-key="id"
			:disabled="store.read_only"
		>
			<template #item="{ element }">
				<Field
					:column="column"
					:field="element"
					:data-is-user-generated="store.is_user_generated_field(element)"
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
	border: 1px dashed var(--gray-400);
	padding: 0.5rem;
	margin-left: 4px;
	margin-right: 4px;

	&.hovered,
	&.selected {
		border-color: var(--primary);
		border-style: solid;

		.btn.btn-icon {
			opacity: 1 !important;
		}
	}

	&.selected {
		.column-header {
			display: flex;
		}

		.column-container {
			height: 80%;
		}
	}

	.column-header {
		display: none;
		align-items: center;
		justify-content: space-between;
		padding-bottom: 0.5rem;
		padding-left: 0.3rem;

		&.has-label {
			display: flex;
		}

		.column-label {
			:deep(span) {
				font-weight: 600;
				color: var(--heading-color);
			}
		}

		.column-actions {
			display: flex;
			justify-content: flex-end;

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

	.column-description {
		margin-bottom: 10px;
		margin-left: 0.3rem;
		font-size: var(--text-xs);
		color: var(--text-muted);
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
}
</style>
