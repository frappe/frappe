<template>
	<button
		ref="add_field_btn_ref"
		class="add-field-btn btn btn-xs btn-icon"
		:title="tooltip"
		@click.stop="toggle_fieldtype_options"
	>
		<slot>
			{{ __("Add field") }}
		</slot>
		<Teleport to="#autocomplete-area">
			<div class="autocomplete" ref="autocomplete_ref">
				<div v-show="show">
					<Autocomplete
						v-model:show="show"
						:value="autocomplete_value"
						:options="fields"
						@change="add_new_field"
						:placeholder="__('Search fieldtypes...')"
					/>
				</div>
			</div>
		</Teleport>
	</button>
</template>

<script setup>
import Autocomplete from "./Autocomplete.vue";
import { useStore } from "../store";
import { clone_field } from "../utils";
import { createPopper } from "@popperjs/core";
import { computed, nextTick, ref, watch } from "vue";
import { onClickOutside } from "@vueuse/core";

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
	tooltip: {
		type: String,
		default: __("Add field"),
	},
});

const emit = defineEmits(["update:modelValue"]);

const selected = computed(() => {
	let fieldname = props.field ? props.field.df.name : props.column.df.name;
	return store.selected(fieldname);
});

const show = ref(false);
const autocomplete_value = ref("");
const fields = computed(() => {
	let fields = frappe.model.all_fieldtypes
		.filter((df) => {
			if (in_list(frappe.model.layout_fields, df)) {
				return false;
			}
			return true;
		})
		.map((df) => {
			let out = { label: __(df), value: df };
			return out;
		});
	return [...fields];
});

const add_field_btn_ref = ref(null);
const autocomplete_ref = ref(null);
const popper = ref(null);

onClickOutside(add_field_btn_ref, () => (show.value = false), { ignore: [autocomplete_ref] });

function setupPopper() {
	if (!popper.value) {
		popper.value = createPopper(add_field_btn_ref.value, autocomplete_ref.value, {
			placement: "bottom-start",
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

function toggle_fieldtype_options() {
	show.value = !show.value;
	autocomplete_value.value = "";
	nextTick(() => setupPopper());
}

function add_new_field(field) {
	fieldtype = field?.value;

	if (!fieldtype) return;

	let new_field = {
		df: store.get_df(fieldtype),
		table_columns: [],
	};

	let cloned_field = clone_field(new_field);

	// insert new field after current field
	let index = 0;
	if (props.field) {
		index = props.column.fields.indexOf(props.field);
	}
	props.column.fields.splice(index + 1, 0, cloned_field);
	store.form.selected_field = cloned_field.df;
	show.value = false;
}

watch(selected, (val) => {
	if (!val) show.value = false;
});

defineExpose({ open: toggle_fieldtype_options });
</script>

<style lang="scss" scoped>
.autocomplete {
	z-index: 100;
}
</style>
