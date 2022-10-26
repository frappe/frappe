<script setup>
import draggable from "vuedraggable";
import Column from "./Column.vue";
import { ref, computed } from "vue";
import { useStore } from "../store";
import { section_boilerplate } from "../utils";

let props = defineProps(["tab", "section"]);
let store = useStore();

let hovered = ref(false);

function add_section_above() {
	let index = props.tab.sections.indexOf(props.section);
	props.tab.sections.splice(index, 0, section_boilerplate());
}

function remove_section() {
	if (store.is_customize_form && props.section.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	} else {
		props.section.columns.forEach((column, i) => {
			if (store.is_custom(column) == 0) {
				frappe.msgprint(
					__("Column {0} is a standard field and it cannot be deleted.", [i + 1])
				);
				throw "cannot delete standard field";
			} else {
				column.fields.forEach(field => {
					if (store.is_custom(field) == 0) {
						frappe.msgprint(
							__(
								"Field <b>{0}</b> inside the section is a standard field. Remove the field from the section and try again.",
								[field.df.label]
							)
						);
						throw "cannot delete standard field";
					}
				});
			}
		});
	}
	frappe.confirm(
		__(
			"All the fields inside the section will also be removed, are you sure you want to continue?"
		),
		() => {
			props.section.remove = true;
			props.section.columns = [];
		},
	);
}

let section_options = computed(() => {
	return [
		{
			label: __("Add section above"),
			action: add_section_above,
		},
		{
			label: __("Remove section"),
			action: remove_section,
		}
	].filter(option => (option.condition ? option.condition() : true));
});
</script>

<template>
	<div class="form-section-container" v-if="!section.remove">
		<div
			:class="[
				'form-section',
				hovered ? 'hovered' : '',
				store.selected(section.df.name) ? 'selected' : ''
			]"
			:title="section.df.fieldname"
			:data-is-custom="store.is_custom(section)"
			@click="store.selected_field = section.df"
			@mouseover.stop="hovered = true"
			@mouseout.stop="hovered = false"
		>
			<div :class="['section-header', section.df.label ? '' : 'hidden']">
				<input
					class="input-section-label"
					type="text"
					:placeholder="__('Section Title')"
					v-model="section.df.label"
				/>
				<div class="section-actions" :hidden="store.read_only">
					<div class="dropdown">
						<button
							class="btn btn-xs btn-section dropdown-button"
							data-toggle="dropdown"
						>
							<div v-html="frappe.utils.icon('dot-horizontal', 'sm')"></div>
						</button>
						<div class="dropdown-menu dropdown-menu-right" role="menu">
							<button
								v-for="(option, i) in section_options"
								:key="i"
								class="dropdown-item"
								@click="option.action"
							>
								{{ option.label }}
							</button>
						</div>
					</div>
				</div>
			</div>
			<div class="section-columns">
				<draggable
					class="section-columns-container"
					v-model="section.columns"
					group="columns"
					item-key="id"
				>
					<template #item="{ element }">
						<Column
							:section="section"
							:column="element"
							:data-is-custom="store.is_custom(element)"
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

	&:last-child {
		border-bottom: none;
	}
	.form-section {
		background-color: var(--fg-color);
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
			display: flex !important;
		}

		.section-header {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding-bottom: 0.75rem;

			.input-section-label {
				border: 1px solid transparent;
				border-radius: var(--border-radius);
				font-size: var(--text-md);
				font-weight: 600;

				&:focus {
					border-color: var(--border-color);
					outline: none;
					background-color: var(--control-bg);
				}

				&::placeholder {
					font-style: italic;
					font-weight: normal;
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
		}
	}
}
</style>
