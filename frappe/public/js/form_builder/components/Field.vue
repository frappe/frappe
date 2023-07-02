<script setup>
import EditableInput from "./EditableInput.vue";
import { ref, computed } from "vue";
import { useStore } from "../store";
import { move_children_to_parent, clone_field } from "../utils";

const props = defineProps(["column", "field"]);
let store = useStore();

let hovered = ref(false);
let component = computed(() => {
	return props.field.df.fieldtype.replace(" ", "") + "Control";
});

function remove_field() {
	if (store.is_customize_form && props.field.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	}
	let index = props.column.fields.indexOf(props.field);
	props.column.fields.splice(index, 1);
	store.form.selected_field = null;
}

function move_fields_to_column() {
	let current_section = store.current_tab.sections.find(section =>
		section.columns.find(column => column == props.column)
	);
	move_children_to_parent(props, "column", "field", current_section);
}

function duplicate_field() {
	let duplicate_field = clone_field(props.field);

	if (store.is_customize_form) {
		duplicate_field.df.is_custom_field = 1;
	}

	if (duplicate_field.df.label) {
		duplicate_field.df.label = duplicate_field.df.label + " Copy";
	}
	duplicate_field.df.fieldname = "";
	duplicate_field.df.__islocal = 1;
	duplicate_field.df.__unsaved = 1;
	duplicate_field.df.owner = frappe.session.user;

	delete duplicate_field.df.creation;
	delete duplicate_field.df.modified;
	delete duplicate_field.df.modified_by;

	// push duplicate_field after props.field in the same column
	let index = props.column.fields.indexOf(props.field);
	props.column.fields.splice(index + 1, 0, duplicate_field);
	store.form.selected_field = duplicate_field.df;
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
		@click.stop="store.form.selected_field = field.df"
		@mouseover.stop="hovered = true"
		@mouseout.stop="hovered = false"
	>
		<component
			:is="component"
			:df="field.df"
			:data-fieldname="field.df.fieldname"
			:data-fieldtype="field.df.fieldtype"
		>
			<template #label>
				<div class="field-label">
					<EditableInput
						:text="field.df.label"
						:placeholder="__('Label')"
						:empty_label="`${__('No Label')} (${field.df.fieldtype})`"
						v-model="field.df.label"
					/>
					<div class="reqd-asterisk" v-if="field.df.reqd">*</div>
					<div class="help-icon" v-if="field.df.documentation_url" v-html="frappe.utils.icon('help', 'sm')"></div>
				</div>
			</template>
			<template #actions>
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
						:title="
							__('Move the current field and the following fields to a new column')
						"
						@click="move_fields_to_column"
					>
						<div v-html="frappe.utils.icon('move', 'sm')"></div>
					</button>
					<button class="btn btn-xs btn-icon" @click.stop="duplicate_field">
						<div v-html="frappe.utils.icon('duplicate', 'sm')"></div>
					</button>
					<button class="btn btn-xs btn-icon" @click.stop="remove_field">
						<div v-html="frappe.utils.icon('remove', 'sm')"></div>
					</button>
				</div>
			</template>
		</component>
	</div>
</template>

<style lang="scss" scoped>
.field {
	text-align: left;
	width: 100%;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius-sm);
	border: 1px solid transparent;
	padding: 0.3rem;
	font-size: var(--text-sm);

	&:not(:first-child) {
		margin-top: 0.4rem;
	}

	&.hovered,
	&.selected {
		border-color: var(--primary);
		.btn.btn-icon {
			opacity: 1 !important;
		}
	}

	:deep(.form-control:read-only:focus) {
		box-shadow: none;
	}

	:deep(.field-controls) {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.3rem;

		.field-label {
			display: flex;
			align-items: center;
			.reqd-asterisk {
				margin-left: 3px;
				color: var(--red-400);
			}
			.help-icon {
				margin-left: 3px;
				color: var(--text-muted);
				cursor: pointer;
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
}
</style>
