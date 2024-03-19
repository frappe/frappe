<script setup>
import EditableInput from "./EditableInput.vue";
import { useStore } from "../store";
import { move_children_to_parent, clone_field } from "../utils";
import { ref, computed, onMounted } from "vue";
import AddFieldButton from "./AddFieldButton.vue";
import { useMagicKeys, whenever } from "@vueuse/core";

const props = defineProps(["column", "field"]);
const store = useStore();

const add_field_ref = ref(null);

// cmd/ctrl + shift + n to open the add field autocomplete
const { ctrl_shift_n, Backspace } = useMagicKeys();
whenever(ctrl_shift_n, (value) => {
	if (value && selected.value) {
		add_field_ref.value.open();
	}
});

// delete/backspace to delete the field
whenever(Backspace, (value) => {
	if (value && selected.value && store.not_using_input) {
		remove_field();
	}
});

const label_input = ref(null);
const hovered = ref(false);
const selected = computed(() => store.selected(props.field.df.name));
const component = computed(() => {
	return props.field.df.fieldtype.replaceAll(" ", "") + "Control";
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
	let current_section = store.current_tab.sections.find((section) =>
		section.columns.find((column) => column == props.column)
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

onMounted(() => selected.value && label_input.value.focus_on_label());
</script>

<template>
	<div
		:class="['field', selected ? 'selected' : hovered ? 'hovered' : '']"
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
						ref="label_input"
						:text="field.df.label"
						:placeholder="__('Label')"
						:empty_label="`${__('No Label')} (${field.df.fieldtype})`"
						v-model="field.df.label"
					/>
					<div class="reqd-asterisk" v-if="field.df.reqd">*</div>
					<div
						class="help-icon"
						v-if="field.df.documentation_url"
						v-html="frappe.utils.icon('help', 'sm')"
					></div>
				</div>
			</template>
			<template #actions>
				<div class="field-actions" :hidden="store.read_only">
					<AddFieldButton
						v-if="column.fields.indexOf(field) != column.fields.length - 1"
						ref="add_field_ref"
						:field="field"
						:column="column"
						:tooltip="__('Add field below')"
					>
						<div v-html="frappe.utils.icon('add', 'sm')" />
					</AddFieldButton>
					<button
						class="btn btn-xs btn-icon"
						:title="__('Duplicate field')"
						@click.stop="duplicate_field"
					>
						<div v-html="frappe.utils.icon('duplicate', 'sm')"></div>
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
					<button
						class="btn btn-xs btn-icon"
						:title="__('Remove field')"
						@click.stop="remove_field"
					>
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
		border-color: var(--border-primary);
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
