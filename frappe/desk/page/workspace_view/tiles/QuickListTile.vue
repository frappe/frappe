<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Badge, Button, LoadingIndicator } from "frappe-ui";
import { post } from "../api.js";
import DeskFilter from "./DeskFilter.vue";

const props = defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const __ = window.__;
const doctype = computed(() => props.widget.document_type);

const rows = ref(null);
const title_field = ref("name");
const can_create = ref(false);
const filters = ref(frappe.utils.process_filter_expression(props.widget.quick_list_filter) || []);

// The newest four rows, with the fields the list view itself asks for.
async function load() {
	rows.value = null;
	const doctype = props.widget.document_type;
	if (!doctype) return (rows.value = []);
	await new Promise((resolve) => frappe.model.with_doctype(doctype, resolve));
	const meta = frappe.get_meta(doctype);
	title_field.value = meta?.title_field || "name";
	can_create.value = frappe.model.can_create(doctype);

	const fields = ["name", title_field.value, "modified"];
	if (frappe.meta.has_field(doctype, "status")) fields.push("status", "docstatus");
	const workflow_field = frappe.workflow.get_state_fieldname(doctype);
	if (workflow_field) fields.push(workflow_field);
	for (const field of frappe.listview_settings?.[doctype]?.add_fields || []) {
		if (frappe.meta.has_field(doctype, field)) fields.push(field);
	}

	const data = await post("frappe.desk.reportview.get", {
		doctype,
		fields: [...new Set(fields)],
		filters: filters.value,
		order_by: "creation desc",
		start: 0,
		page_length: 4,
	});
	rows.value = Array.isArray(data) ? data : frappe.utils.dict(data.keys, data.values);
}

onMounted(load);
watch(doctype, load);

function set_filters(next) {
	filters.value = next;
	load();
}

function indicator(doc) {
	return frappe.get_indicator(doc, doctype.value);
}

function open(doc, event) {
	if (event.ctrlKey || event.metaKey) frappe.open_in_new_tab = true;
	frappe.set_route(frappe.utils.get_form_link(doctype.value, doc.name));
}

function open_list(event) {
	if (event.ctrlKey || event.metaKey) frappe.open_in_new_tab = true;
	const route_filters = frappe.utils.get_filter_from_json(JSON.stringify(filters.value));
	if (route_filters) frappe.route_options = route_filters;
	frappe.set_route(frappe.utils.generate_route({ type: "doctype", name: doctype.value }));
}

function add_new() {
	frappe.ui.form.make_quick_entry(doctype.value, () => load());
}

function text(value) {
	return new DOMParser().parseFromString(String(value ?? ""), "text/html").body.textContent;
}
</script>

<template>
	<div class="flex h-full flex-col rounded-6 border border-outline-gray-1 bg-surface-base p-4">
		<div class="mb-2 flex items-center justify-between gap-2">
			<span class="truncate text-base font-medium text-ink-gray-8">{{ widget.label }}</span>
			<div class="flex shrink-0 items-center gap-1">
				<DeskFilter
					v-if="doctype"
					:key="doctype"
					:doctype="doctype"
					:filters="filters"
					@change="set_filters"
				/>
				<Button
					size="sm"
					variant="ghost"
					icon="lucide-refresh-cw"
					:label="__('Refresh List')"
					@click="load"
				/>
				<Button
					v-if="can_create"
					size="sm"
					variant="ghost"
					icon="lucide-plus"
					:label="__('Add New') + ' ' + __(doctype)"
					@click="add_new"
				/>
			</div>
		</div>
		<div class="min-h-0 flex-1 overflow-hidden">
			<LoadingIndicator v-if="!rows" class="size-4 text-ink-gray-4" />
			<p v-else-if="!rows.length" class="text-base text-ink-gray-5">
				{{ __("No Data...") }}
			</p>
			<button
				v-for="doc in rows"
				v-else
				:key="doc.name"
				type="button"
				class="flex w-full items-center gap-2 rounded px-1 py-1.5 text-left hover:bg-surface-gray-2"
				@click="open(doc, $event)"
			>
				<span class="min-w-0 flex-1">
					<span class="block truncate text-base text-ink-gray-8">
						{{ text(doc[title_field]) }}
					</span>
					<span class="block text-sm text-ink-gray-5">
						{{ frappe.datetime.prettyDate(doc.modified) }}
					</span>
				</span>
				<Badge
					v-if="indicator(doc)"
					:label="indicator(doc)[0]"
					:theme="indicator(doc)[1]"
				/>
			</button>
		</div>
		<Button class="mt-1 self-start" size="sm" :label="__('View List')" @click="open_list" />
	</div>
</template>
