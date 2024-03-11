<script setup>
import SearchBox from "./SearchBox.vue";
import { evaluate_depends_on_value } from "../utils";
import { ref, computed } from "vue";
import { useStore } from "../store";

let store = useStore();

let search_text = ref("");
let args = ref({});

let docfield_df = computed(() => {
	let fields = store.get_docfields.filter((df) => {
		if (in_list(frappe.model.layout_fields, df.fieldtype) || df.hidden) {
			return false;
		}
		if (
			df.depends_on &&
			!evaluate_depends_on_value(df.depends_on, store.form.selected_field)
		) {
			return false;
		}

		if (df.fieldname === "fetch_from") {
			df.fieldtype = "Fetch From";
		}

		if (
			["fetch_from", "fetch_if_empty"].includes(df.fieldname) &&
			in_list(frappe.model.no_value_type, store.form.selected_field.fieldtype)
		) {
			return false;
		}

		if (df.fieldname === "reqd" && store.form.selected_field.fieldtype === "Check") {
			return false;
		}

		if (df.fieldname === "options") {
			df.fieldtype = "Small Text";
			df.options = "";
			args.value = {};

			if (["Table", "Link"].includes(store.form.selected_field.fieldtype)) {
				df.fieldtype = "Link";
				df.options = "DocType";

				if (store.form.selected_field.fieldtype === "Table") {
					args.value.is_table_field = 1;
				}
			}
		}

		// show link_filters docfield only when link field is selected
		if (df.fieldname === "link_filters" && store.form.selected_field.fieldtype !== "Link") {
			return false;
		}

		if (search_text.value) {
			if (
				df.label.toLowerCase().includes(search_text.value.toLowerCase()) ||
				df.fieldname.toLowerCase().includes(search_text.value.toLowerCase())
			) {
				return true;
			}
			return false;
		}
		return true;
	});
	return [...fields];
});
</script>

<template>
	<div class="header">
		<SearchBox class="flex-1" v-model="search_text" />
		<button
			class="close-btn btn btn-xs"
			:title="__('Close properties')"
			@click="store.form.selected_field = null"
		>
			<div v-html="frappe.utils.icon('remove', 'sm')"></div>
		</button>
	</div>
	<div class="control-data">
		<div v-if="store.form.selected_field">
			<div class="field" v-for="(df, i) in docfield_df" :key="i">
				<component
					:is="df.fieldtype.replaceAll(' ', '') + 'Control'"
					:args="args"
					:df="df"
					:read_only="store.read_only"
					:value="store.form.selected_field[df.fieldname]"
					v-model="store.form.selected_field[df.fieldname]"
					:data-fieldname="df.fieldname"
					:data-fieldtype="df.fieldtype"
				/>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.header {
	display: flex;
	padding: 5px;
	border-bottom: 1px solid var(--border-color);

	.close-btn {
		margin-right: -5px;
	}
}
.control-data {
	height: calc(100vh - 202px);
	overflow-y: auto;
	padding: 8px;

	.field {
		margin: 5px;
		margin-top: 0;
		margin-bottom: 1rem;

		:deep(.form-control:disabled) {
			color: var(--disabled-text-color);
			background-color: var(--disabled-control-bg);
			cursor: default;
		}
	}
}
</style>
