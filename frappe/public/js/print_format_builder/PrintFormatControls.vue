<template>
	<div class="layout-side-section">
		<div class="form-sidebar">
			<div class="sidebar-menu">
				<div class="sidebar-label">{{ __("Page Margins") }}</div>
				<div class="margin-controls">
					<div class="form-group" v-for="df in margins" :key="df.fieldname">
						<div class="clearfix">
							<label class="control-label"> {{ df.label }} </label>
						</div>
						<div class="control-input-wrapper">
							<div class="control-input">
								<input
									type="number"
									class="form-control form-control-sm"
									:value="print_format[df.fieldname]"
									@change="e => update_margin(df.fieldname, e.target.value)"
								/>
							</div>
						</div>
					</div>
				</div>
			</div>
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
						v-for="df in fields"
						:key="df.fieldname"
						:title="df.fieldname"
					>
						{{ df.label }}
					</div>
				</draggable>
			</div>
		</div>
	</div>
</template>

<script>
import draggable from "vuedraggable";
import { get_table_columns, pluck } from "./utils";
import { storeMixin } from "./store";

export default {
	name: "PrintFormatControls",
	mixins: [storeMixin],
	data() {
		return {
			search_text: ""
		};
	},
	components: {
		draggable
	},
	methods: {
		update_margin(fieldname, value) {
			value = parseFloat(value);
			if (value < 0) {
				value = 0;
			}
			this.$store.print_format[fieldname] = value;
		},
		clone_field(df) {
			let cloned = pluck(df, [
				"label",
				"fieldname",
				"fieldtype",
				"options",
				"table_columns",
				"html"
			]);
			if (cloned.custom) {
				// generate unique fieldnames for custom blocks
				cloned.fieldname += "_" + frappe.utils.get_random(8);
			}
			return cloned;
		}
	},
	computed: {
		margins() {
			return [
				{ label: __("Top"), fieldname: "margin_top" },
				{ label: __("Bottom"), fieldname: "margin_bottom" },
				{ label: __("Left"), fieldname: "margin_left" },
				{ label: __("Right"), fieldname: "margin_right" }
			];
		},
		fields() {
			let fields = this.meta.fields
				.filter(df => {
					if (["Section Break", "Column Break"].includes(df.fieldtype)) {
						return false;
					}
					if (this.search_text) {
						if (df.fieldname.includes(this.search_text)) {
							return true;
						}
						if (df.label && df.label.includes(this.search_text)) {
							return true;
						}
						return false;
					} else {
						return true;
					}
				})
				.map(df => {
					let out = {
						label: df.label,
						fieldname: df.fieldname,
						fieldtype: df.fieldtype,
						options: df.options
					};
					if (df.fieldtype == "Table") {
						out.table_columns = get_table_columns(df);
					}
					return out;
				});

			return [
				{
					label: __("Custom HTML"),
					fieldname: "custom_html",
					fieldtype: "HTML",
					html: "",
					custom: 1
				},
				{
					label: __("ID (name)"),
					fieldname: "name",
					fieldtype: "Data"
				},
				...fields
			];
		}
	}
};
</script>

<style scoped>
.margin-controls {
	display: flex;
}

.margin-controls .form-control {
	background: white;
}

.margin-controls > .form-group + .form-group {
	margin-left: 0.5rem;
}

.fields-container {
	max-height: calc(100vh - 22rem);
	overflow-y: auto;
}

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
}

.field:not(:first-child) {
	margin-top: 0.5rem;
}

.sidebar-menu:last-child {
	margin-bottom: 0;
}
</style>
