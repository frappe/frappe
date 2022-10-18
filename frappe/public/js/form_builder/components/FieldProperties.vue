<script setup>
import SearchBox from "./SearchBox.vue";
import { evaluate_depends_on_value } from "../utils";
import { ref, computed } from "vue";
import { useStore } from "../store";

let store = useStore();

let search_text = ref("");

let docfield_df = computed(() => {
	let fields = store.docfields.filter(df => {
		if (
			in_list(["Tab Break", "Section Break", "Column Break", "Fold"], df.fieldtype) ||
			!df.label
		) {
			return false;
		}
		if (df.depends_on && !evaluate_depends_on_value(df.depends_on, store.selected_field)) {
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
		} else {
			return true;
		}
	});

	return [...fields];
});
</script>

<template>
	<SearchBox v-model="search_text" />
	<div class="control-data">
		<div v-if="store.selected_field">
			<div class="field" v-for="(df, i) in docfield_df" :key="i">
				<div class="label">{{ df.label }}</div>
				<div class="input">
					<input
						class="mb-2 form-control form-control-sm"
						type="text"
						v-model="store.selected_field[df.fieldname]"
					/>
				</div>
				<div class="description" v-if="df.description">{{ df.description }}</div>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.control-data {
	max-height: calc(100vh - 240px);
	overflow-y: auto;

	.field {
		margin: 5px;
		margin-top: 0;
		margin-bottom: 1rem;

		.label {
			margin-bottom: 0.3rem;
		}
		.description {
			font-size: var(--text-sm);
			color: var(--text-muted);
		}
	}
}

</style>
