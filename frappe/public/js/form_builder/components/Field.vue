<script setup>
import EditableInput from "./EditableInput.vue";
import { ref, computed } from "vue";
import { useStore } from "../store";
import { move_children_to_parent } from "../utils";

let props = defineProps(["column", "field"]);
let store = useStore();

let hovered = ref(false);
let component = computed(() => {
	return props.field.df.fieldtype.replace(' ', '') + 'Control';
});

function remove_field() {
	if (store.is_customize_form && props.field.df.is_custom_field == 0) {
		frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
		throw "cannot delete standard field";
	}
	let index = props.column.fields.indexOf(props.field);
	props.column.fields.splice(index, 1);
}

function move_fields_to_column() {
	let current_section = store.current_tab.sections.find(section =>
		section.columns.find(column => column == props.column)
	);
	move_children_to_parent(props, "column", "field", current_section);
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
		@click.stop="store.selected_field = field.df"
		@mouseover.stop="hovered = true"
		@mouseout.stop="hovered = false"
		@mousemove.stop="store.drag = true"
		@mousedown.stop="store.drag = false"
		@mouseup.stop="store.start_drag(field)"
	>
		<component :is="component" :df="field.df">
			<template #label>
				<EditableInput
					:class="{ reqd: field.df.reqd }"
					:text="field.df.label"
					:placeholder="__('Label')"
					:empty_label="`${__('No Label')} (${field.df.fieldtype})`"
					v-model="field.df.label"
				/>
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
						<div
							:style="{ strokeWidth: 0.6 }"
							v-html="frappe.utils.icon('arrow-up-right', 'sm')"
						></div>
					</button>
					<button class="btn btn-xs btn-icon" @click="remove_field">
						<div v-html="frappe.utils.icon('close', 'sm')"></div>
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

	:deep(.field-controls) {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.3rem;

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
