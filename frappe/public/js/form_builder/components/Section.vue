<template>
	<div
		class="form-section-container"
		:style="{ borderBottom: props.section.df.hide_border ? 'none' : '' }"
	>
		<div
			:class="[
				'form-section',
				hovered ? 'hovered' : '',
				store.selected(section.df.name) ? 'selected' : '',
			]"
			:title="section.df.fieldname"
			@click.stop="select_section"
			@mouseover.stop="hovered = true"
			@mouseout.stop="hovered = false"
		>
			<div
				:class="[
					'section-header',
					section.df.label || section.df.collapsible ? 'has-label' : '',
					collapsed ? 'collapsed' : '',
				]"
				:hidden="!section.df.label && store.read_only"
			>
				<div class="section-label">
					<EditableInput
						:text="section.df.label"
						:placeholder="__('Section Title')"
						v-model="section.df.label"
					/>
					<div
						v-if="section.df.collapsible"
						class="collapse-indicator"
						v-html="frappe.utils.icon(collapsed ? 'down' : 'up-line', 'sm')"
					></div>
				</div>
				<Dropdown v-if="!store.read_only" :options="options" @click.stop />
			</div>
			<div v-if="section.df.description" class="section-description">
				{{ section.df.description }}
			</div>
			<div
				class="section-columns"
				:class="{
					hidden: section.df.collapsible && collapsed,
					'has-one-column': section.columns.length === 1,
				}"
			>
				<draggable
					class="section-columns-container"
					v-model="section.columns"
					group="columns"
					item-key="id"
					:delay="is_touch_screen_device() ? 200 : 0"
					:animation="200"
					:easing="store.get_animation"
					:disabled="store.read_only"
				>
					<template #item="{ element }">
						<Column
							:section="section"
							:column="element"
							:data-is-user-generated="store.is_user_generated_field(element)"
						/>
					</template>
				</draggable>
			</div>
		</div>
	</div>
</template>

<script setup>
import draggable from "vuedraggable";
import Column from "./Column.vue";
import EditableInput from "./EditableInput.vue";
import Dropdown from "./Dropdown.vue";
import { ref, computed } from "vue";
import { useStore } from "../store";
import {
	section_boilerplate,
	move_children_to_parent,
	confirm_dialog,
	is_touch_screen_device,
} from "../utils";
import { useMagicKeys, whenever } from "@vueuse/core";

const props = defineProps(["tab", "section"]);
const store = useStore();

// delete/backspace to delete the field
const { Backspace } = useMagicKeys();
whenever(Backspace, (value) => {
	if (value && selected.value && store.not_using_input) {
		remove_section();
	}
});

const hovered = ref(false);
const collapsed = ref(false);
const selected = computed(() => store.selected(props.section.df.name));
const column = computed(() => props.section.columns[props.section.columns.length - 1]);

// section
function add_section_below() {
	let index = props.tab.sections.indexOf(props.section);
	props.tab.sections.splice(index + 1, 0, section_boilerplate());
}

function is_section_empty() {
	return !props.section.columns.some(
		(column) => (store.is_customize_form && !column.df.is_custom_field) || column.fields.length
	);
}

function remove_section() {
	if (store.is_customize_form && props.section.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	} else if (store.has_standard_field(props.section)) {
		delete_section();
	} else if (is_section_empty()) {
		delete_section(true);
	} else {
		confirm_dialog(
			__("Delete Section", null, "Title of confirmation dialog"),
			__(
				"Are you sure you want to delete the section? All the columns along with fields in the section will be moved to the previous section.",
				null,
				"Confirmation dialog message"
			),
			() => delete_section(),
			__("Delete section", null, "Button text"),
			() => delete_section(true),
			__("Delete entire section with fields", null, "Button text")
		);
	}
}

function delete_section(with_children) {
	let sections = props.tab.sections;
	let index = sections.indexOf(props.section);

	if (!with_children) {
		if (index > 0) {
			let prev_section = sections[index - 1];
			if (!is_section_empty()) {
				// move all columns from current section to previous section
				prev_section.columns = [...prev_section.columns, ...props.section.columns];
			}
		} else if (index == 0 && !is_section_empty()) {
			// create a new section and push columns to it
			sections.unshift({
				df: store.get_df("Section Break"),
				columns: props.section.columns,
				is_first: true,
			});
			index++;
		}
	}

	// remove section
	sections.splice(index, 1);
	store.form.selected_field = null;
}

function select_section() {
	if (props.section.df.collapsible) {
		collapsed.value = !collapsed.value;
	}
	store.form.selected_field = props.section.df;
}

function move_sections_to_tab() {
	let new_tab = move_children_to_parent(props, "tab", "section", store.form.layout);

	// activate tab
	store.form.active_tab = new_tab;
}

// column
function add_column() {
	props.section.columns.push({
		fields: [],
		df: store.get_df("Column Break"),
	});
}

function remove_column() {
	if (store.is_customize_form && column.value.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	} else if (column.value.fields.length == 0 || store.has_standard_field(column.value)) {
		delete_column();
	} else {
		confirm_dialog(
			__("Delete Column", null, "Title of confirmation dialog"),
			__(
				"Are you sure you want to delete the column? All the fields in the column will be moved to the previous column.",
				null,
				"Confirmation dialog message"
			),
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
	let index = columns.length - 1;

	if (with_children && index == 0 && columns.length == 1) {
		if (column.value.fields.length == 0) {
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
			prev_column.fields = [...prev_column.fields, ...column.value.fields];
		} else {
			if (column.value.fields.length == 0) {
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
					fields: column.value.fields,
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

const options = computed(() => {
	let groups = [
		{
			group: __("Section"),
			items: [
				{ label: __("Add section below"), onClick: add_section_below },
				{ label: __("Remove section"), onClick: remove_section },
			],
		},
		{
			group: __("Column"),
			items: [{ label: __("Add column"), onClick: add_column }],
		},
	];

	// add remove column option if there are more than one columns
	if (props.section.columns.length > 1) {
		groups[1].items.push({
			label: __("Remove column"),
			tooltip: __("Remove last column"),
			onClick: remove_column,
		});
	} else if (props.section.columns[0].fields.length) {
		// add remove all fields option if there is only one column and it has fields
		groups[1].items.push({
			label: __("Empty column"),
			tooltip: __("Remove all fields in the column"),
			onClick: () => delete_column(true),
		});
	}

	// add move to tab option if the current section is not the first section
	if (props.tab.sections.indexOf(props.section) > 0) {
		groups[0].items.push({
			label: __("Move sections to new tab"),
			tooltip: __("Move current and all subsequent sections to a new tab"),
			onClick: move_sections_to_tab,
		});
	}

	return groups;
});
</script>

<style lang="scss" scoped>
.form-section-container {
	border-bottom: 1px solid var(--border-color);
	background-color: var(--fg-color);

	&:last-child {
		border-bottom: none;
	}

	.form-section {
		background-color: inherit;
		border: 1px solid transparent;
		border-radius: var(--border-radius);
		padding: 1rem;
		cursor: pointer;

		&:last-child {
			border-bottom-left-radius: var(--border-radius);
			border-bottom-right-radius: var(--border-radius);
		}

		&.hovered,
		&.selected {
			border-color: var(--border-primary);
		}

		.section-header {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding-bottom: 0.75rem;

			&.collapsed {
				padding-bottom: 0;
			}

			&.has-label {
				display: flex;
			}

			.section-label {
				display: flex;

				:deep(span) {
					font-weight: 600;
					color: var(--heading-color);
				}

				.collapse-indicator {
					margin-left: 7px;
				}
			}

			.section-actions {
				display: flex;
				gap: 4px;
				align-items: center;
			}

			// .btn-section {
			// 	padding: var(--padding-xs);
			// 	box-shadow: none;

			// 	&:hover {
			// 		background-color: var(--bg-light-gray);
			// 	}
			// }
			.btn-section {
				display: inline-flex;
				gap: 2px;
			}
		}

		.section-description {
			margin-bottom: 10px;
			font-size: var(--text-xs);
			color: var(--text-muted);
		}

		.section-columns-container {
			display: flex;
			min-height: 2rem;
			border-radius: var(--border-radius);
		}
	}
}
</style>
