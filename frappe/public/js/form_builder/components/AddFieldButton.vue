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
						:placeholder="
							store.is_web_form ? __('Search fields...') : __('Search fieldtypes...')
						"
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
	// a Web Form offers the source doctype's own fields, every other builder offers fieldtypes
	if (store.is_web_form) return unplaced_source_fields();

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
	let value = field?.value;

	if (!value) return;

	let df;
	if (store.is_web_form) {
		// the picker offers the source doctype's own fields, so `value` is a fieldname
		let source_df = store.source_doctype_fields.find((f) => f.fieldname === value);
		if (!source_df) return;

		df = store.get_df(source_df.fieldtype, source_df.fieldname, source_df.label);
		// Link/Select/Table are unusable without options
		df.options = source_df.options;
		df.reqd = source_df.reqd;
	} else {
		df = store.get_df(value);
	}

	let new_field = {
		df,
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

// the source doctype's fields that are not on the canvas yet
function unplaced_source_fields() {
	let placed = new Set(
		store.form.layout.tabs.flatMap((t) =>
			t.sections.flatMap((s) =>
				s.columns.flatMap((c) => c.fields.map((f) => f.df.fieldname))
			)
		)
	);

	return store.source_doctype_fields
		.filter(
			(df) => !frappe.model.layout_fields.includes(df.fieldtype) && !placed.has(df.fieldname)
		)
		.map((df) => ({
			// Autocomplete sorts on label, and a doctype's fields need not have one
			label: __(df.label) || frappe.unscrub(df.fieldname),
			value: df.fieldname,
		}));
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
