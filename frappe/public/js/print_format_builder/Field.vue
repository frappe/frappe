<template>
	<div class="field" :title="df.fieldname" @click="editing = true">
		<div class="field-controls">
			<div>
				<div
					class="custom-html"
					v-if="df.fieldtype == 'HTML' && df.html"
					v-html="df.html"
				></div>
				<div class="custom-html" v-if="df.fieldtype == 'Field Template'">
					{{ df.label }}
				</div>
				<input
					v-else-if="editing && df.fieldtype != 'HTML'"
					ref="label-input"
					class="label-input"
					type="text"
					:placeholder="__('Label')"
					v-model="df.label"
					@keydown.enter="editing = false"
					@blur="editing = false"
				/>
				<span v-else-if="df.label">{{ df.label }}</span>
				<i class="text-muted" v-else> {{ __("No Label") }} ({{ df.fieldname }}) </i>
			</div>
			<div class="field-actions">
				<button
					v-if="df.fieldtype == 'HTML'"
					class="btn btn-xs btn-icon"
					@click="edit_html"
				>
					<svg class="icon icon-sm">
						<use href="#icon-edit"></use>
					</svg>
				</button>
				<button
					v-if="df.fieldtype == 'Table'"
					class="btn btn-xs btn-default"
					@click="configure_columns"
				>
					Configure columns
				</button>
				<button class="btn btn-xs btn-icon" @click="$set(df, 'remove', true)">
					<svg class="icon icon-sm">
						<use href="#icon-close"></use>
					</svg>
				</button>
			</div>
		</div>
		<div
			v-if="df.fieldtype == 'Table'"
			class="table-controls row no-gutters"
			:style="{ opacity: 1 }"
		>
			<div
				class="table-column"
				:style="{ width: tf.width + '%' }"
				v-for="(tf, i) in df.table_columns"
				:key="tf.fieldname"
			>
				<div class="table-field">
					{{ tf.label }}
				</div>
			</div>
		</div>
	</div>
</template>
<script>
import draggable from "vuedraggable";
import ConfigureColumnsVue from "./ConfigureColumns.vue";
import { storeMixin } from "./store";

export default {
	name: "Field",
	mixins: [storeMixin],
	props: ["df"],
	components: {
		draggable,
	},
	data() {
		return {
			editing: false,
		};
	},
	watch: {
		editing(value) {
			if (value) {
				this.$nextTick(() => this.$refs["label-input"].focus());
			}
		},
		"df.table_columns": {
			deep: true,
			handler() {
				this.validate_table_columns();
			},
		},
	},
	methods: {
		edit_html() {
			let d = new frappe.ui.Dialog({
				title: __("Edit HTML"),
				fields: [
					{
						label: __("HTML"),
						fieldname: "html",
						fieldtype: "Code",
						options: "HTML",
					},
				],
				primary_action: ({ html }) => {
					html = frappe.dom.remove_script_and_style(html);
					this.$set(this.df, "html", html);
					d.hide();
				},
			});
			d.set_value("html", this.df.html);
			d.show();
		},
		configure_columns() {
			let dialog = new frappe.ui.Dialog({
				title: __("Configure columns for {0}", [this.df.label]),
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "columns_area",
					},
					{
						label: "",
						fieldtype: "Autocomplete",
						placeholder: __("Add Column"),
						fieldname: "add_column",
						options: this.get_all_columns(),
						onchange: () => {
							let fieldname = dialog.get_value("add_column");
							if (fieldname) {
								let column = this.get_column_to_add(fieldname);
								if (column) {
									this.df.table_columns.push(column);
									this.$set(this.df, "table_columns", this.df.table_columns);
									dialog.set_value("add_column", "");
								}
							}
						},
					},
				],
				on_page_show: () => {
					new Vue({
						el: dialog.get_field("columns_area").$wrapper.get(0),
						render: (h) =>
							h(ConfigureColumnsVue, {
								props: {
									df: this.df,
								},
							}),
					});
				},
				on_hide: () => {
					this.$set(
						this.df,
						"table_columns",
						this.df.table_columns.filter((col) => !col.invalid_width)
					);
				},
			});
			dialog.show();
		},
		get_all_columns() {
			let meta = frappe.get_meta(this.df.options);
			let more_columns = [
				{
					label: __("Sr No."),
					value: "idx",
				},
			];
			return more_columns.concat(
				meta.fields
					.map((tf) => {
						if (frappe.model.no_value_type.includes(tf.fieldtype)) {
							return;
						}
						return {
							label: tf.label,
							value: tf.fieldname,
						};
					})
					.filter(Boolean)
			);
		},
		get_column_to_add(fieldname) {
			let standard_columns = {
				idx: {
					label: __("Sr No."),
					fieldtype: "Data",
					fieldname: "idx",
					width: 10,
				},
			};

			if (fieldname in standard_columns) {
				return standard_columns[fieldname];
			}

			return {
				...frappe.meta.get_docfield(this.df.options, fieldname),
				width: 10,
			};
		},
		validate_table_columns() {
			if (this.df.fieldtype != "Table") return;

			let columns = this.df.table_columns;
			let total_width = 0;
			for (let column of columns) {
				if (!column.width) {
					column.width = 10;
				}
				total_width += column.width;
				if (total_width > 100) {
					column.invalid_width = true;
				} else {
					column.invalid_width = false;
				}
			}
		},
	},
};
</script>
<style>
.field {
	text-align: left;
	width: 100%;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius);
	border: 1px dashed var(--gray-400);
	padding: 0.5rem 0.75rem;
	font-size: var(--text-sm);
}

.field-controls {
	display: flex;
	justify-content: space-between;
	align-items: center;
}

.field:not(:first-child) {
	margin-top: 0.5rem;
}

.custom-html {
	padding-right: var(--padding-xs);
	word-break: break-all;
}

.label-input {
	background-color: transparent;
	border: none;
	padding: 0;
}

.label-input:focus {
	outline: none;
}

.field:focus-within {
	border-style: solid;
	border-color: var(--gray-600);
}

.field-actions {
	flex: none;
}

.field-actions .btn {
	opacity: 0;
}

.field-actions .btn-icon {
	box-shadow: none;
}

.btn-icon {
	padding: 2px;
}

.btn-icon:hover {
	background-color: white;
}

.field:hover .btn {
	opacity: 1;
}

.table-controls {
	display: flex;
	margin-top: 1rem;
}

.table-column {
	position: relative;
}

.table-field {
	text-align: left;
	width: 100%;
	background-color: white;
	border-radius: var(--border-radius);
	border: 1px dashed var(--gray-400);
	padding: 0.5rem 0.75rem;
	font-size: var(--text-sm);
	user-select: none;
	white-space: nowrap;
	overflow: hidden;
}

.column-resize {
	position: absolute;
	right: 0;
	top: 0;
	width: 6px;
	border-radius: 2px;
	height: 80%;
	background-color: var(--gray-600);
	transform: translate(50%, 10%);
	z-index: 999;
	cursor: col-resize;
}

.column-resize-actions {
	position: absolute;
	top: 0;
	right: 0;
	height: 100%;
	display: flex;
	align-items: center;
	padding-right: 0.25rem;
}

.column-resize-actions .btn-icon {
	background: white;
}
.column-resize-actions .btn-icon:hover {
	background: var(--bg-light-gray);
}

.columns-input {
	padding: var(--padding-sm);
}
</style>
