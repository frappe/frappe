<script setup>
import { get_table_columns, load_doctype_model } from "../../utils";
import { computedAsync } from "@vueuse/core";

const props = defineProps(["df", "is-customize-form"]);

let table_columns = computedAsync(async () => {
	let doctype = props.df.options;
	if (!doctype) return [];
	if (!frappe.get_meta(doctype)) {
		await load_doctype_model(doctype);
	}
	let child_doctype = frappe.get_meta(doctype);
	return get_table_columns(props.df, child_doctype);
}, []);

function open_new_child_doctype_dialog() {
	let is_custom = props.isCustomizeForm;
	frappe.model.with_doctype("DocType").then(() => {
		frappe.listview_settings["DocType"].new_doctype_dialog({ is_child: 1, is_custom });
	});
}
</script>

<template>
	<div class="control editable">
		<!-- label -->
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>

		<!-- table grid -->
		<div
			v-if="df.fieldtype == 'Table'"
			class="table-controls row no-gutters"
			:style="{ opacity: 1 }"
		>
			<div
				class="table-column"
				:style="{ width: size * 10 + '%' }"
				v-for="([tf, size], i) in table_columns"
				:key="i"
			>
				<div class="table-field ellipsis">
					{{ __(tf.label) }}
				</div>
			</div>
		</div>
		<div class="grid-empty text-center">
			<img
				src="/assets/frappe/images/ui-states/grid-empty-state.svg"
				:alt="__('Grid Empty State')"
				class="grid-empty-illustration"
			/>
			<!-- render this button when there are no columns, which means that options is not added for the table -->
			<button
				class="btn btn-xs btn-secondary"
				@click="open_new_child_doctype_dialog"
				v-if="!table_columns.length"
			>
				{{ __("Create Child Doctype") }}
			</button>
			<p v-else>{{ __("No Data") }}</p>
		</div>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="__(df.description)"></div>
	</div>
</template>

<style lang="scss" scoped>
.grid-empty {
	background-color: var(--fg-color);
	border-bottom-left-radius: var(--border-radius);
	border-bottom-right-radius: var(--border-radius);
	border: 1px solid var(--table-border-color);
}
.table-controls {
	display: flex;

	.table-column {
		position: relative;

		.table-field {
			background-color: var(--fg-color);
			border: 1px solid var(--table-border-color);
			border-left: none;
			padding: 8px 10px;
			user-select: none;
			white-space: nowrap;
			overflow: hidden;
		}
		&:first-child .table-field {
			border-top-left-radius: var(--border-radius);
			border-left: 1px solid var(--table-border-color);
		}
		&:last-child .table-field {
			border-top-right-radius: var(--border-radius);
		}
	}
}
</style>
