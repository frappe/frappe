<script setup>
import draggable from "vuedraggable";
import Column from "./Column.vue";
import EditableInput from "./EditableInput.vue";
import { ref } from "vue";
import { useStore } from "../store";
import { section_boilerplate, move_children_to_parent, confirm_dialog } from "../utils";

const props = defineProps(["tab", "section"]);
let store = useStore();

let hovered = ref(false);
let collapsed = ref(false);

function add_section_above() {
	let index = props.tab.sections.indexOf(props.section);
	props.tab.sections.splice(index, 0, section_boilerplate());
}

function is_section_empty() {
	return !props.section.columns.some(
		column => (store.is_customize_form && !column.df.is_custom_field) || column.fields.length
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
			__("Are you sure you want to delete the section? All the columns along with fields in the section will be moved to the previous section.", null, "Confirmation dialog message"),
			() => delete_section(),
			__("Delete section", null, "Button text"),
			() => delete_section(true),
			__("Delete entire section with columns", null, "Button text")
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
</script>

<template>
	<div
		class="form-section-container"
		:style="{ borderBottom: props.section.df.hide_border ? 'none' : '' }"
	>
		<div
			:class="[
				'form-section',
				hovered ? 'hovered' : '',
				store.selected(section.df.name) ? 'selected' : ''
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
					collapsed ? 'collapsed' : ''
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
						v-html="frappe.utils.icon( collapsed ? 'down' : 'up-line', 'sm' )"
					></div>
				</div>
				<div class="section-actions" :hidden="store.read_only">
					<button
						v-if="tab.sections.indexOf(section)"
						class="btn btn-xs btn-section"
						:title="__('Move the current section and the following sections to a new tab')"
						@click="move_sections_to_tab"
					>
						<div v-html="frappe.utils.icon('move', 'sm')"></div>
					</button>
					<button
						class="btn btn-xs btn-section"
						:title="__('Add section above')"
						@click="add_section_above"
					>
						<div v-html="frappe.utils.icon('add', 'sm')"></div>
					</button>
					<button
						class="btn btn-xs btn-section"
						:title="__('Remove section')"
						@click.stop="remove_section"
					>
						<div v-html="frappe.utils.icon('remove', 'sm')"></div>
					</button>
				</div>
			</div>
			<div v-if="section.df.description" class="section-description">{{ section.df.description }}</div>
			<div
				class="section-columns"
				:class="{
					hidden: section.df.collapsible && collapsed,
					'has-one-column': section.columns.length === 1
				}"
			>
				<draggable
					class="section-columns-container"
					:style="{
						backgroundColor: section.columns.length ? null : 'var(--field-placeholder-color)'
					}"
					v-model="section.columns"
					group="columns"
					item-key="id"
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
			border-color: var(--primary);
		}

		&.selected .section-header {
			display: flex;
		}

		.section-header {
			display: none;
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
				align-items: center;
			}

			.btn-section {
				padding: var(--padding-xs);
				box-shadow: none;

				&:hover {
					background-color: var(--bg-light-gray);
				}
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
