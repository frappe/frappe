<script setup>
import SearchBox from "./SearchBox.vue";
import { evaluate_depends_on_value } from "../utils";
import { ref, computed } from "vue";
import { useStore } from "../store";

let store = useStore();

let search_text = ref("");

let docfield_df = computed(() => {
	let fields = store.get_docfields.filter(df => {
		if (in_list(frappe.model.layout_fields, df.fieldtype) || df.hidden) {
			return false;
		}
		if (df.depends_on && !evaluate_depends_on_value(df.depends_on, store.selected_field)) {
			return false;
		}

		if (df.fieldname === "options") {
			df.fieldtype = "Small Text";
			df.options = "";

			if (in_list(["Table", "Link"], store.selected_field.fieldtype)) {
				df.fieldtype = "Link";
				df.options = "DocType";

				if (store.selected_field.fieldtype === "Table") {
					df.is_table_field = 1;
				}
			}
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
	<SearchBox v-model="search_text" />
	<div class="control-data">
		<div v-if="store.selected_field">
			<div class="field" v-for="(df, i) in docfield_df" :key="i">
				<component
					:is="df.fieldtype.replace(' ', '') + 'Control'"
					:df="df"
					:value="store.selected_field[df.fieldname]"
					v-model="store.selected_field[df.fieldname]"
				/>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.control-data {
	height: calc(100vh - 250px);
	overflow-y: auto;
	padding: 8px;

	.field {
		margin: 5px;
		margin-top: 0;
		margin-bottom: 1rem;
	}
}
</style>
