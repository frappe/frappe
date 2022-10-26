<script setup>
import draggable from "vuedraggable";
import Field from "./Field.vue";
import { ref, computed } from "vue";
import { useStore } from "../store";

let props = defineProps(["section"]);
let emit = defineEmits(["add_section_above"]);
let store = useStore();

let hovered = ref(false);

let visible_columns = computed(() => props.section.columns.filter(c => !c.remove));

function add_column() {
	if (visible_columns.value.length < 4) {
		props.section.columns.push({
			df: store.get_df("Column Break", "column_break_" + frappe.utils.get_random(4)),
			fields: [],
		});
	}
}
function remove_column() {
	if (visible_columns.value.length <= 1) return;

	// get last column's index
	let index = visible_columns.value.length - 1;

	if (store.is_customize_form && store.is_custom(visible_columns.value[index]) == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	}

	let columns = visible_columns.value.slice();
	let last_column_fields = columns.slice(-1)[0].fields.slice();

	// remove last column
	columns = columns.slice(0, index);

	// move fields from last column to second last column
	let last_column = columns[index - 1];
	last_column.fields = [...last_column.fields, ...last_column_fields];

	props.section.columns = columns;
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
			action: () => emit("add_section_above"),
		},
		{
			label: __("Add column"),
			action: add_column,
			condition: () => visible_columns.value.length < 4,
		},
		{
			label: __("Remove column"),
			action: remove_column,
			condition: () => visible_columns.value.length > 1,
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
				<div
					class="column col"
					v-for="(column, i) in visible_columns"
					:key="i"
					@mouseover.stop="hovered = false"
				>
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
							<Field :field="element" :data-is-custom="store.is_custom(element)" />
						</template>
					</draggable>
				</div>
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

			&.hidden {
				display: none;
			}

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

		.section-columns {
			display: flex;
			flex-wrap: wrap;

			.column {
				padding-left: 8px;
				padding-right: 8px;

				&:first-child {
					padding-left: 0px;
				}

				&:last-child {
					padding-right: 0px;
				}

				.column-container {
					height: 100%;
					min-height: 2rem;
					border-radius: var(--border-radius);
				}
			}
		}
	}
}
</style>
