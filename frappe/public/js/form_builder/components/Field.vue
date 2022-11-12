<script setup>
import { ref, nextTick } from "vue";
import { useStore } from "../store";
import { move_children_to_parent } from "../utils";

let props = defineProps(["column", "field"]);
let store = useStore();

let label_input = ref(null);
let editing = ref(false);
let hovered = ref(false);

function remove_field() {
	if (store.is_customize_form && props.field.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	}
	let index = props.column.fields.indexOf(props.field);
	props.column.fields.splice(index, 1);
}

function select_field() {
	if (!store.read_only) {
		editing.value = true;
		nextTick(() => label_input.value.focus());
	}
	store.selected_field = props.field.df;
}

function move_fields_to_column() {
	let current_section = store.current_tab.sections.find(section =>
		section.columns.find(column => column == props.column)
	);
	move_children_to_parent(props, "column", "field", current_section);
}
</script>

<template>
	<div
		:class="[
			'field',
			hovered ? 'hovered' : '',
			store.selected(field.df.name) ? 'selected' : ''
		]"
		:title="field.df.fieldname"
		@click.stop="select_field"
		@mouseover.stop="hovered = true"
		@mouseout.stop="hovered = false"
	>
		<div class="field-controls">
			<div :class="{ 'reqd': field.df.reqd }">
				<input
					v-if="editing"
					ref="label_input"
					class="label-input"
					:disabled="store.read_only"
					type="text"
					:placeholder="__('Label')"
					v-model="field.df.label"
					@keydown.enter="editing = false"
					@blur="editing = false"
				/>
				<span v-else-if="field.df.label">{{ field.df.label }}</span>
				<i class="text-muted" v-else> {{ __("No Label") }} ({{ field.df.fieldtype }}) </i>
			</div>
			<div class="field-actions" :hidden="store.read_only">
				<button
					v-if="field.df.fieldtype == 'HTML'"
					class="btn btn-xs btn-icon"
					@click="edit_html"
				>
					<div v-html="frappe.utils.icon('edit', 'sm')"></div>
				</button>
				<button
					v-if="column.fields.indexOf(field)"
					class="btn btn-xs btn-icon"
					:title="__('Move the current field and the following fields to a new column')"
					@click="move_fields_to_column"
				>
					<div
						:style="{ strokeWidth: 0.6 }"
						v-html="frappe.utils.icon('arrow-up-right', 'sm')"
					></div>
				</button>
				<button class="btn btn-xs btn-icon" @click="remove_field">
					<div v-html="frappe.utils.icon('close', 'sm')"></div>
				</button>
			</div>
		</div>
		<div
			v-if="field.df.fieldtype == 'Table'"
			class="table-controls row no-gutters"
			:style="{ opacity: 1 }"
		>
			<div
				class="table-column"
				:style="{ width: tf.width + '%' }"
				v-for="tf in field.table_columns"
				:key="tf.fieldname"
			>
				<div class="table-field">
					{{ tf.label }}
				</div>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.field {
	text-align: left;
	width: 100%;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius);
	border: 1px solid var(--gray-400);
	padding: 0.5rem 0.75rem;
	font-size: var(--text-sm);

	&:not(:first-child) {
		margin-top: 0.5rem;
	}

	&.hovered,
	&.selected {
		border-color: var(--primary);
		.btn.btn-icon {
			opacity: 1 !important;
		}
	}

	.field-controls {
		display: flex;
		justify-content: space-between;
		align-items: center;

		.reqd::after {
			content: " *";
			color: var(--red-400);
		}

		.label-input {
			background-color: transparent;
			border: none;
			padding: 0;

			&:focus {
				outline: none;
			}
		}

		.field-actions {
			flex: none;

			.btn.btn-icon {
				opacity: 0;
				box-shadow: none;
				padding: 2px;

				&:hover {
					background-color: var(--fg-color);
				}
			}
		}
	}

	.table-controls {
		display: flex;
		margin-top: 1rem;

		.table-column {
			position: relative;

			.table-field {
				text-align: left;
				width: 100%;
				background-color: white;
				border-radius: var(--border-radius);
				border: 1px dashed var(--gray-400);
				padding: 0.5rem 0.75rem;
				font-size: var(--text-sm);
				user-select: none;
				white-space: nowrap;
				overflow: hidden;
			}
		}
	}
}
</style>
