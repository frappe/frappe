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
			new_field: true,
			fields: [],
		});
	}
}
function remove_column() {
	if (visible_columns.value.length <= 1) return;

	let columns = visible_columns.value.slice();
	let last_column_fields = columns.slice(-1)[0].fields.slice();

	// remove last column
	let index = columns.length - 1;
	columns = columns.slice(0, index);

	// move fields from last column to second last column
	let last_column = columns[index - 1];
	last_column.fields = [...last_column.fields, ...last_column_fields];

	props.section.columns = columns;
}
function remove_section() {
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
				<div class="d-flex align-items-center">
					<div class="dropdown">
						<button
							class="btn btn-xs btn-section dropdown-button"
							data-toggle="dropdown"
						>
							<svg class="icon icon-sm">
								<use href="#icon-dot-horizontal"></use>
							</svg>
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
						:animation="150"
						item-key="id"
					>
						<template #item="{ element }">
							<Field :field="element" />
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

		&:not(:first-child) {
			margin-top: 1rem;
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
