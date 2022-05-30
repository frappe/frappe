<template>
	<div class="layout-side-section">
		<div class="form-sidebar">
			<div class="sidebar-menu">
				<div class="sidebar-label">{{ __("Page Margins") }}</div>
				<div class="margin-controls">
					<div
						class="form-group"
						v-for="df in margins"
						:key="df.fieldname"
					>
						<div class="clearfix">
							<label class="control-label">
								{{ df.label }}
							</label>
						</div>
						<div class="control-input-wrapper">
							<div class="control-input">
								<input
									type="number"
									class="form-control form-control-sm"
									:value="print_format[df.fieldname]"
									min="0"
									@change="
										e =>
											update_margin(
												df.fieldname,
												e.target.value
											)
									"
								/>
							</div>
						</div>
					</div>
				</div>
			</div>
			<div class="sidebar-menu">
				<div class="sidebar-label">{{ __("Google Font") }}</div>
				<div class="form-group">
					<div class="control-input-wrapper">
						<div class="control-input">
							<select
								class="form-control form-control-sm"
								v-model="print_format.font"
							>
								<option
									v-for="font in google_fonts"
									:value="font"
								>
									{{ font }}
								</option>
							</select>
						</div>
					</div>
				</div>
			</div>
			<div class="sidebar-menu">
				<div class="sidebar-label">{{ __("Font Size") }}</div>
				<div class="form-group">
					<div class="control-input-wrapper">
						<div class="control-input">
							<input
								type="number"
								class="form-control form-control-sm"
								placeholder="12, 13, 14"
								:value="print_format.font_size"
								@change="
									e =>
										(print_format.font_size = parseFloat(
											e.target.value
										))
								"
							/>
						</div>
					</div>
				</div>
			</div>
			<div class="sidebar-menu">
				<div class="sidebar-label">{{ __("Page Number") }}</div>
				<div class="form-group">
					<div class="control-input-wrapper">
						<div class="control-input">
							<select
								class="form-control form-control-sm"
								v-model="print_format.page_number"
							>
								<option
									v-for="position in page_number_positions"
									:value="position.value"
								>
									{{ position.label }}
								</option>
							</select>
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
import { get_table_columns, resolve_fields_from_path, pluck } from "./utils";
import { storeMixin } from "./store";

const DEFAULT_FIELDS = [
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
	{
		label: __("Spacer"),
		fieldname: "spacer",
		fieldtype: "Spacer",
		custom: 1
	},
	{
		label: __("Divider"),
		fieldname: "divider",
		fieldtype: "Divider",
		custom: 1
	}
]

export default {
	name: "PrintFormatControls",
	mixins: [storeMixin],
	data() {
		return {
			fields: [],
			search_text: "",
			google_fonts: []
		};
	},
	watch: {
		search_text: frappe.utils.debounce(async function (value) {
			await this.get_fields(value)
		}, 500)
	},
	components: {
		draggable
	},
	async created() {
		await this.get_fields("")
	},
	mounted() {
		let method =
			"frappe.printing.page.print_format_builder_beta.print_format_builder_beta.get_google_fonts";
		frappe.call(method).then(r => {
			this.google_fonts = r.message || [];
			if (!this.google_fonts.includes(this.print_format.font)) {
				this.google_fonts.push(this.print_format.font);
			}
		});
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
				"html",
				"field_template",
				"ancestors"
			]);
			if (cloned.custom) {
				// generate unique fieldnames for custom blocks
				cloned.fieldname += "_" + frappe.utils.get_random(8);
			}
			return cloned;
		},
		async get_fields(search_text) {
			let path = []
			const parts = this.search_text.split(".")
			if (parts.length > 1) {
				search_text = parts[parts.length - 1]
				path = parts.slice(0, parts.length - 1)
			}

			search_text = search_text.toLowerCase()

			let fields = await resolve_fields_from_path(this.meta.fields, path)

			fields = fields
				.filter(df => !["Section Break", "Column Break"].includes(df.fieldtype))
				.map(df => {
					let out = {
						label: df.label,
						fieldname: df.fieldname,
						fieldtype: df.fieldtype,
						options: df.options,
						ancestors: Array.from(path)
					};
					if (df.fieldtype == "Table") {
						out.table_columns = get_table_columns(df);
					}
					return out;
				});

			fields = path.length > 0 ? fields : [
				...DEFAULT_FIELDS,
				...this.print_templates,
				...fields
			]

			this.fields = (
				fields.filter((field => field.fieldname.toLowerCase().includes(search_text)
				|| field.label.toLowerCase().includes(search_text)))
			)
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
		print_templates() {
			let templates = this.print_format.__onload.print_templates || {};
			let out = [];
			for (let template of templates) {
				let df;
				if (template.field) {
					df = frappe.meta.get_docfield(
						this.meta.name,
						template.field
					);
				} else {
					df = {
						label: template.name,
						fieldname: frappe.scrub(template.name)
					};
				}
				out.push({
					label: `${__(df.label)} (${__("Field Template")})`,
					fieldname: df.fieldname + "_template",
					fieldtype: "Field Template",
					field_template: template.name
				});
			}
			return out;
		},
		page_number_positions() {
			return [
				{ label: __("Hide"), value: "Hide" },
				{ label: __("Top Left"), value: "Top Left" },
				{ label: __("Top Center"), value: "Top Center" },
				{ label: __("Top Right"), value: "Top Right" },
				{ label: __("Bottom Left"), value: "Bottom Left" },
				{ label: __("Bottom Center"), value: "Bottom Center" },
				{ label: __("Bottom Right"), value: "Bottom Right" }
			];
		}
	}
};
</script>

<style scoped>
.margin-controls {
	display: flex;
}

.form-control {
	background: var(--control-bg-on-gray);
}

.margin-controls > .form-group + .form-group {
	margin-left: 0.5rem;
}

.margin-controls > .form-group {
	margin-bottom: 0;
}

.fields-container {
	max-height: calc(100vh - 34rem);
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

.control-font >>> .frappe-control[data-fieldname="font"] label {
	display: none;
}
</style>
