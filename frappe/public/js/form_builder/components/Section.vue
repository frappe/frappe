<script setup>
import draggable from "vuedraggable";
import Column from "./Column.vue";
import EditableInput from "./EditableInput.vue";
import { ref } from "vue";
import { useStore } from "../store";
import { section_boilerplate } from "../utils";

let props = defineProps(["tab", "section"]);
let store = useStore();

let hovered = ref(false);
let collapsed = ref(false);

function add_section_above() {
	let index = props.tab.sections.indexOf(props.section);
	props.tab.sections.splice(index, 0, section_boilerplate());
}

function is_section_empty() {
	return !props.section.columns.some(column => column.fields.length);
}

function remove_section() {
	if (store.is_customize_form && props.section.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	}

	let sections = props.tab.sections;
	let index = sections.indexOf(props.section);

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

	// remove section
	sections.splice(index, 1);
}

function select_section() {
	if (props.section.df.collapsible) {
		collapsed.value = !collapsed.value;
	}
	store.selected_field = props.section.df;
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
				:class="['section-header', section.df.label || section.df.collapsible ? 'has-label' : '']"
				:hidden="!section.df.label && store.read_only"
				:style="{ paddingBottom: !collapsed ? '0.75rem' : '' }"
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
						class="btn btn-xs btn-section"
						:title="__('Add section above')"
						@click="add_section_above"
					>
						<div v-html="frappe.utils.icon('add', 'sm')"></div>
					</button>
					<button
						class="btn btn-xs btn-section"
						:title="__('Remove section')"
						@click="remove_section"
					>
						<div v-html="frappe.utils.icon('close', 'sm')"></div>
					</button>
				</div>
			</div>
			<div class="section-columns" :class="{ hidden: section.df.collapsible && collapsed }">
				<draggable
					class="section-columns-container"
					:style="{
						backgroundColor: section.columns.length ? null : 'var(--gray-50)'
					}"
					v-model="section.columns"
					filter="[data-has-std-field='true']"
					:prevent-on-filter="false"
					group="columns"
					item-key="id"
					:disabled="store.read_only"
				>
					<template #item="{ element }">
						<Column
							:section="section"
							:column="element"
							:data-is-custom="element.df.is_custom_field"
							:data-has-std-field="store.has_standard_field(element)"
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

			&.has-label {
				display: flex;
			}

			.section-label {
				display: flex;

				:deep(span) {
					font-weight: 600;
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

		.section-columns-container {
			display: flex;
			min-height: 2rem;
			border-radius: var(--border-radius);
		}
	}
}
</style>
