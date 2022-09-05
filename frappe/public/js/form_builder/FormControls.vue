<template>
	<div class="layout-side-section">
		<div class="form-sidebar">
			<div class="sidebar-menu">
				<div class="sidebar-label">{{ __("Fields") }}</div>
				<input
					class="mb-2 form-control form-control-sm"
					type="text"
					:placeholder="__('Search fields')"
					v-model="search_text"
				/>
				<draggable
					class="fields-container"
					:list="fields"
					:group="{ name: 'fields', pull: 'clone', put: false }"
					:sort="false"
					:clone="clone_field"
				>
					<div
						class="field"
						v-for="(df, i) in fields"
						:key="i"
						:title="df.fieldtype"
					>
						{{ df.fieldtype }}
					</div>
				</draggable>
			</div>
		</div>
	</div>
</template>

<script>
import draggable from "vuedraggable";
import { pluck } from "./utils";
import { storeMixin } from "./store";

export default {
	name: "FormControls",
	mixins: [storeMixin],
	data() {
		return {
			search_text: "",
		};
	},
	components: {
		draggable
	},
	methods: {
		clone_field(df) {
			let cloned = pluck(df, [
				"label",
				"fieldname",
				"fieldtype",
				"options",
				"table_columns",
				"new_field"
			]);
			if (cloned.custom) {
				// generate unique fieldnames for custom blocks
				cloned.fieldname += "_" + frappe.utils.get_random(8);
			}
			return cloned;
		}
	},
	computed: {
		fields() {
			let fields = frappe.model.all_fieldtypes
				.filter(df => {
					if (
						["Tab Break", "Section Break", "Column Break", "Fold"].includes(df)
					) {
						return false;
					}
					if (this.search_text) {
						if (df.toLowerCase().includes(this.search_text.toLowerCase())) {
							return true;
						}
						return false;
					} else {
						return true;
					}
				})
				.map(df => {
					let out = {
						label: "",
						fieldname: "",
						fieldtype: df,
						options: "",
						new_field: true,
					};
					return out;
				});

			return [...fields];
		}
	}
};
</script>

<style lang="scss" scoped>
.layout-side-section {
	padding: 0;

	.form-control {
		background: var(--control-bg-on-gray);
	}

	.fields-container {
		max-height: calc(100vh - 14rem);
		overflow-y: auto;

		.field {
			display: flex;
			justify-content: space-between;
			align-items: center;
			width: 100%;
			background-color: var(--bg-light-gray);
			border-radius: var(--border-radius);
			border: 1px dashed var(--gray-400);
			padding: 0.5rem 0.75rem;
			font-size: var(--text-sm);
			cursor: pointer;

			&:not(:first-child) {
				margin-top: 0.5rem;
			}
		}
	}
}
</style>
