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

function make_dialog(frm) {
	frm.dialog = new frappe.ui.Dialog({
		title: __("Set Filters"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "filter_area",
			},
		],
		primary_action: () => {
			let fieldname = props.field.df.fieldname;
			let field_option = props.field.df.options;
			let filters = frm.filter_group.get_filters().map((filter) => {
				// last element is a boolean which hides the filter hence not required to store in meta
				filter.pop();

				// filter_group component requires options and frm.set_query requires fieldname so storing both
				filter[0] = field_option;
				return filter;
			});

			props.field.df.link_filters = JSON.stringify(filters);
			store.form.selected_field = props.field.df;
			frm.dialog.hide();
		},
		primary_action_label: __("Apply"),
	});

	if (frm.doctype === "Customize Form") {
		let current_doctype = frm.doc.doc_type;
		let fieldname = props.field.df.fieldname;
		let property = "link_filters";
		let property_setter_id = current_doctype + "-" + fieldname + "-" + property;

		frappe.db.exists("Property Setter", property_setter_id).then((exits) => {
			if (exits) {
				frm.dialog.set_secondary_action_label(__("Reset To Default"));
				frm.dialog.set_secondary_action(() => {
					frappe.call({
						method: "frappe.custom.doctype.customize_form.customize_form.get_link_filters_from_doc_without_customisations",
						args: {
							doctype: current_doctype,
							fieldname: fieldname,
						},
						callback: function (r) {
							if (r.message) {
								props.field.df.link_filters = r.message;

								frm.filter_group.clear_filters();
								add_existing_filter(frm, props.field.df);
								// hide the secondary action button
								frm.dialog.get_secondary_btn().addClass("hidden");
							}
						},
					});
				});
			}
		});
	}
}

function make_filter_area(frm, doctype) {
	frm.filter_group = new frappe.ui.FilterGroup({
		parent: frm.dialog.get_field("filter_area").$wrapper,
		doctype: doctype,
		on_change: () => {},
	});
}

function add_existing_filter(frm, df) {
	if (df.link_filters) {
		let filters = JSON.parse(df.link_filters);
		if (filters) {
			frm.filter_group.add_filters_to_filter_group(filters);
		}
	}
}

function edit_filters() {
	let field_doctype = props.field.df.options;
	const { frm } = store;

	make_dialog(frm);
	make_filter_area(frm, field_doctype);
	frappe.model.with_doctype(field_doctype, () => {
		frm.dialog.show();
		add_existing_filter(frm, props.field.df);
	});
}

function is_filter_applied() {
	if (props.field.df.link_filters) {
		try {
			if (JSON.parse(props.field.df.link_filters).length > 0) {
				return "btn-filter-applied";
			}
		} catch (error) {
			return "";
		}
	}
}

function open_child_doctype() {
	if (!props.field?.df?.options) return;
	window.open(`/app/doctype/${props.field.df.options}`, "_blank");
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
			:is-customize-form="store.is_customize_form"
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
					/>
				</div>
			</template>
			<template #actions>
				<div class="field-actions" :hidden="store.read_only">
					<button
						v-if="field.df.fieldtype === 'Link'"
						class="btn btn-xs btn-icon"
						:class="is_filter_applied()"
						@click="edit_filters"
					>
						<div v-html="frappe.utils.icon('filter', 'sm')" />
					</button>
					<AddFieldButton ref="add_field_ref" :column="column" :field="field">
						<div v-html="frappe.utils.icon('add', 'sm')" />
					</AddFieldButton>
					<button
						v-if="column.fields.indexOf(field)"
						class="btn btn-xs btn-icon"
						:title="
							__('Move the current field and the following fields to a new column')
						"
						@click="move_fields_to_column"
					>
						<div v-html="frappe.utils.icon('move', 'sm')" />
					</button>
					<button
						class="btn btn-xs btn-icon"
						:title="__('Duplicate field')"
						@click.stop="duplicate_field"
					>
						<div v-html="frappe.utils.icon('duplicate', 'sm')" />
					</button>
					<button
						v-if="field.df.fieldtype === 'Table' && field.df.options"
						class="btn btn-xs btn-icon"
						@click="open_child_doctype"
						:title="__('Edit the {0} Doctype', [field.df.options])"
					>
						<div v-html="frappe.utils.icon('external-link', 'sm')" />
					</button>
					<button
						class="btn btn-xs btn-icon"
						:title="__('Remove field')"
						@click.stop="remove_field"
					>
						<div v-html="frappe.utils.icon('remove', 'sm')" />
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
.btn-filter-applied {
	background-color: var(--gray-300) !important;
	&:hover {
		background-color: var(--gray-400) !important;
	}
}
</style>
