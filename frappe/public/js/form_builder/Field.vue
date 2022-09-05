<template>
	<div class="field" :title="df.fieldname" @click="editing = true">
		<div class="field-controls">
			<div>
				<input
					v-if="editing"
					ref="label-input"
					class="label-input"
					type="text"
					:placeholder="__('Label')"
					v-model="df.label"
					@keydown.enter="editing = false"
					@blur="editing = false"
				/>
				<span v-else-if="df.label">{{ df.label }}</span>
				<i class="text-muted" v-else>
					{{ __("No Label") }} ({{ df.fieldtype }})
				</i>
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
					class="btn btn-xs btn-icon"
					@click="$set(df, 'remove', true)"
				>
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
				v-for="tf in df.table_columns"
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
import { storeMixin } from "./store";

export default {
	name: "Field",
	mixins: [storeMixin],
	props: ["df"],
	data() {
		return {
			editing: false
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
			}
		}
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
						options: "HTML"
					}
				],
				primary_action: ({ html }) => {
					html = frappe.dom.remove_script_and_style(html);
					this.$set(this.df, "html", html);
					d.hide();
				}
			});
			d.set_value("html", this.df.html);
			d.show();
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
		}
	}
};
</script>
<style lang="scss" scoped>
.field {
	text-align: left;
	width: 100%;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius);
	border: 1px dashed var(--gray-400);
	padding: 0.5rem 0.75rem;
	font-size: var(--text-sm);

	&:not(:first-child) {
		margin-top: 0.5rem;
	}

	&:focus-within {
		border-style: solid;
		border-color: var(--gray-600);
	}

	&:hover {
		.btn.btn-icon {
			opacity: 1 !important;
		}
	}

	.field-controls {
		display: flex;
		justify-content: space-between;
		align-items: center;

		.label-input {
			background-color: transparent;
			border: none;
			padding: 0;

			&:focus {
				outline: none;
			}
		}

		.field-actions {
			flex: none;

			.btn.btn-icon {
				opacity: 0;
				box-shadow: none;
				padding: 2px;

				&:hover {
					background-color: white;
				}
			}
		}
	}

	.table-controls {
		display: flex;
		margin-top: 1rem;

		.table-column {
			position: relative;

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
		}
	}
}
</style>
