<template>
	<button
		ref="add_field_btn_ref"
		class="add-field-btn btn btn-xs btn-icon"
		:title="__('Add field')"
		@click="toggle_fieldtype_dropdown"
	>
		<slot>
			{{ __("Add a field") }}
		</slot>
		<div class="drop-down" ref="dropdown_ref">
			<Dropdown v-if="show" :items="fields" v-model="search_text" />
		</div>
	</button>
</template>

<script setup>
import Dropdown from "./Dropdown.vue";
import { useStore } from "../store";
import { clone_field } from "../utils";
import { createPopper } from "@popperjs/core";
import { computed, ref, watch } from "vue";

const store = useStore();

const props = defineProps({
	column: {
		type: Object,
		default: null,
	},
	field: {
		type: Object,
		default: null,
	},
});

const emit = defineEmits(["update:modelValue", "update_parent"]);

const selected = computed(() => {
	let fieldname = props.field ? props.field.df.name : props.column.df.name;
	return store.selected(fieldname);
});

const show = ref(false);
const search_text = ref("");
const fields = computed(() => {
	let fields = frappe.model.all_fieldtypes
		.filter((df) => {
			if (in_list(frappe.model.layout_fields, df)) {
				return false;
			}
			if (search_text.value) {
				if (df.toLowerCase().includes(search_text.value.toLowerCase())) {
					return true;
				}
				return false;
			} else {
				return true;
			}
		})
		.map((df) => {
			let out = {
				label: df,
				onClick: () => {
					let new_field = {
						df: store.get_df(df),
						table_columns: [],
					};

					add_new_field(clone_field(new_field));
				},
			};
			return out;
		});
	return [...fields];
});

const add_field_btn_ref = ref(null);
const dropdown_ref = ref(null);
const popper = ref(null);

function setupPopper() {
	if (!popper.value) {
		popper.value = createPopper(add_field_btn_ref.value, dropdown_ref.value, {
			placement: "bottom-end",
			modifiers: [
				{
					name: "offset",
					options: {
						offset: [0, 4],
					},
				},
			],
		});
	} else {
		popper.value.update();
	}
}

function toggle_fieldtype_dropdown() {
	show.value = !show.value;
	search_text.value = "";
	setTimeout(() => setupPopper());
}

function add_new_field(field) {
	// insert new field after current field
	let index = 0;
	if (props.field) {
		index = props.column.fields.indexOf(props.field);
	}
	props.column.fields.splice(index + 1, 0, field);
	store.form.selected_field = field.df;
	show.value = false;
	emit("update_parent");
}

watch(selected, (val) => {
	if (!val) show.value = false;
});
</script>

<style lang="scss" scoped>
.drop-down {
	z-index: 100;
}
</style>
