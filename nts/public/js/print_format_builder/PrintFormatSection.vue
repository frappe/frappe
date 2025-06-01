<template>
	<div class="print-format-section-container" v-if="!section.remove">
		<div class="print-format-section">
			<div class="section-header">
				<input
					class="input-section-label w-50"
					type="text"
					:placeholder="__('Section Title')"
					v-model="section.label"
				/>
				<div class="d-flex align-items-center">
					<div
						class="mr-2 text-small text-muted d-flex"
						v-if="section.field_orientation == 'left-right'"
						:title="
							// prettier-ignore
							__('Render labels to the left and values to the right in this section')
						"
					>
						Label → Value
					</div>
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
								v-for="option in section_options"
								class="dropdown-item"
								@click="option.action"
							>
								{{ option.label }}
							</button>
						</div>
					</div>
				</div>
			</div>
			<div class="row section-columns">
				<div class="column col" v-for="(column, i) in section.columns" :key="i">
					<draggable
						class="drag-container"
						:style="{
							backgroundColor: column.fields.length ? null : 'var(--gray-50)',
						}"
						v-model="column.fields"
						group="fields"
						:animation="150"
						item-key="id"
					>
						<template #item="{ element }">
							<Field :df="element" />
						</template>
					</draggable>
				</div>
			</div>
		</div>
		<div class="my-4 text-center text-muted font-italic" v-if="section.page_break">
			{{ __("Page Break") }}
		</div>
	</div>
</template>

<script setup>
import draggable from "vuedraggable";
import Field from "./Field.vue";
import { computed } from "vue";

// props
const props = defineProps(["section"]);

// emits
let emit = defineEmits(["add_section_above"]);

// methods
function add_column() {
	if (props.section.columns.length < 4) {
		props.section.columns.push({
			label: "",
			fields: [],
		});
	}
}
function remove_column() {
	if (props.section.columns.length <= 1) return;

	let columns = props.section.columns.slice();
	let last_column_fields = columns.slice(-1)[0].fields.slice();
	let index = columns.length - 1;
	columns = columns.slice(0, index);
	let last_column = columns[index - 1];
	last_column.fields = [...last_column.fields, ...last_column_fields];

	props.section["columns"] = columns;
}
function add_page_break() {
	props.section["page_break"] = true;
}
function remove_page_break() {
	props.section["page_break"] = false;
}

// computed
let section_options = computed(() => {
	return [
		{
			label: __("Add section above"),
			action: () => emit("add_section_above"),
		},
		{
			label: __("Add column"),
			action: add_column,
			condition: () => props.section.columns.length < 4,
		},
		{
			label: __("Remove column"),
			action: remove_column,
			condition: () => props.section.columns.length > 1,
		},
		{
			label: __("Add page break"),
			action: add_page_break,
			condition: () => !props.section.page_break,
		},
		{
			label: __("Remove page break"),
			action: remove_page_break,
			condition: () => props.section.page_break,
		},
		{
			label: __("Remove section"),
			action: () => {
				props.section["remove"] = true;
			},
		},
		{
			label: __("Field Orientation (Left-Right)"),
			condition: () => !props.section.field_orientation,
			action: () => {
				props.section["field_orientation"] = "left-right";
			},
		},
		{
			label: __("Field Orientation (Top-Down)"),
			condition: () => props.section.field_orientation == "left-right",
			action: () => {
				props.section["field_orientation"] = "";
			},
		},
	].filter((option) => (option.condition ? option.condition() : true));
});
</script>

<style scoped>
.print-format-section-container:not(:last-child) {
	margin-bottom: 1rem;
}

.print-format-section {
	background-color: white;
	border: 1px solid var(--dark-border-color);
	border-radius: var(--border-radius);
	padding: 1rem;
	cursor: pointer;
}

.section-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding-bottom: 0.75rem;
}

.input-section-label {
	border: 1px solid transparent;
	border-radius: var(--border-radius);
	font-size: var(--text-md);
	font-weight: 600;
}

.input-section-label:focus {
	border-color: var(--border-color);
	outline: none;
	background-color: var(--control-bg);
}

.input-section-label::placeholder {
	font-style: italic;
	font-weight: normal;
}

.btn-section {
	padding: var(--padding-xs);
	box-shadow: none;
}

.btn-section:hover {
	background-color: var(--bg-light-gray);
}

.print-format-section:not(:first-child) {
	margin-top: 1rem;
}

.section-columns {
	margin-left: -8px;
	margin-right: -8px;
}

.column {
	padding-left: 8px;
	padding-right: 8px;
}

.drag-container {
	height: 100%;
	min-height: 2rem;
	border-radius: var(--border-radius);
}
</style>
