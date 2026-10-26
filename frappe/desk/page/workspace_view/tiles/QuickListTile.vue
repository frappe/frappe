<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Badge, Button, ItemListRow } from "frappe-ui";
import { ChartCard, ChartContainer } from "frappe-ui/charts";
import { get, post } from "../api.js";
import DeskFilter from "./DeskFilter.vue";
import { badge_theme } from "./badge_theme.js";

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
const activity = ref({});
const order_by = computed(() => props.widget.order_by || "creation desc");
const sort_field = ref(null);

// `my_activity` orders by the session user's newest action instead of a field
const MY_ACTIVITY = "my_activity";
// the most rows any tile height shows; the tile draws as many as fit
const MAX_ROWS = 20;

// The first rows in the tile's order, with the fields the list view itself asks for.
async function load() {
	rows.value = null;
	const doctype = props.widget.document_type;
	if (!doctype) return (rows.value = []);
	await new Promise((resolve) => frappe.model.with_doctype(doctype, resolve));
	const meta = frappe.get_meta(doctype);
	title_field.value = meta?.title_field || "name";
	can_create.value = frappe.model.can_create(doctype);

	const [fieldname] = order_by.value.split(" ");
	sort_field.value = ["creation", "modified", MY_ACTIVITY].includes(fieldname)
		? null
		: frappe.meta.get_docfield(doctype, fieldname) || null;

	const fields = ["name", title_field.value, "modified"];
	if (sort_field.value) fields.push(sort_field.value.fieldname);
	if (frappe.meta.has_field(doctype, "status")) fields.push("status", "docstatus");
	const workflow_field = frappe.workflow.get_state_fieldname(doctype);
	if (workflow_field) fields.push(workflow_field);
	for (const field of frappe.listview_settings?.[doctype]?.add_fields || []) {
		if (frappe.meta.has_field(doctype, field)) fields.push(field);
	}

	let names = null;
	if (order_by.value === MY_ACTIVITY) {
		const events = await get("frappe.desk.desktop.get_recent_activity", {
			doctype,
			filters: JSON.stringify(filters.value),
			limit: MAX_ROWS,
		});
		activity.value = Object.fromEntries(events.map((event) => [event.name, event]));
		names = events.map((event) => event.name);
		if (!names.length) return (rows.value = []);
	}

	const data = await post("frappe.desk.reportview.get", {
		doctype,
		fields: [...new Set(fields)],
		filters: names ? [...filters.value, [doctype, "name", "in", names]] : filters.value,
		order_by: names ? "creation desc" : order_by.value,
		start: 0,
		page_length: MAX_ROWS,
	});
	const docs = Array.isArray(data) ? data : frappe.utils.dict(data.keys, data.values);
	rows.value = names ? docs.sort((a, b) => names.indexOf(a.name) - names.indexOf(b.name)) : docs;
}

const card = ref(null);
const list = ref(null);
const fit = ref(4);
const max_height = inject("tile_max_height", ref(null));
let observer = null;

// as many whole rows as the tile's largest height holds, so the tile ends at its last row
function measure() {
	const row = list.value?.firstElementChild;
	const card_height = card.value?.$el.offsetHeight;
	if (!row?.offsetHeight || !max_height.value || !card_height) return;
	const room = max_height.value - (card_height - list.value.offsetHeight);
	fit.value = Math.max(1, Math.floor(room / row.offsetHeight));
}

watch(list, (element) => {
	observer?.disconnect();
	if (!element) return;
	observer = new ResizeObserver(measure);
	observer.observe(element);
});
watch([rows, max_height], () => nextTick(measure));
onBeforeUnmount(() => observer?.disconnect());

const visible = computed(() => rows.value?.slice(0, fit.value));

function subtitle(doc) {
	const event = activity.value[doc.name];
	if (order_by.value === MY_ACTIVITY && event) {
		const when = frappe.datetime.prettyDate(event.creation);
		return [event.text || event.action, when].filter(Boolean).join(" · ");
	}
	const df = sort_field.value;
	if (df && doc[df.fieldname]) {
		const value = ["Date", "Datetime"].includes(df.fieldtype)
			? relative(doc[df.fieldname])
			: text(frappe.format(doc[df.fieldname], df, { inline: true }));
		return `${__(df.label)} · ${value}`;
	}
	return frappe.datetime.prettyDate(doc.modified);
}

// "in 3 hours" or "2 days ago", read in the user's timezone as prettyDate reads it
const UNITS = [
	["year", 31536000],
	["month", 2592000],
	["week", 604800],
	["day", 86400],
	["hour", 3600],
	["minute", 60],
];

function relative(value) {
	const parse = (str) => new Date(str.replace(/-/g, "/").replace(/\.[0-9]*/, ""));
	const when = parse(frappe.datetime.convert_to_user_tz(value));
	const seconds = (when - parse(frappe.datetime.now_datetime())) / 1000;
	const [unit, size] = UNITS.find(([, size]) => Math.abs(seconds) >= size) || UNITS.at(-1);
	return new Intl.RelativeTimeFormat(frappe.boot.lang || "en", { numeric: "auto" }).format(
		Math.round(seconds / size),
		unit
	);
}

// a badge every row shares, as when the filter fixes the status, says nothing
const one_status = computed(
	() =>
		visible.value?.length > 1 &&
		new Set(visible.value.map((doc) => indicator(doc)?.[0])).size === 1
);

onMounted(load);
watch([doctype, order_by], load);

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
	<ChartCard ref="card" :style="{ height: !rows && max_height ? `${max_height}px` : null }">
		<ChartContainer :title="widget.label" :loading="!rows" :empty="rows?.length === 0">
			<template #actions>
				<div class="flex items-center gap-1">
					<DeskFilter
						v-if="doctype && !Number(widget.hide_filter)"
						:key="doctype"
						:doctype="doctype"
						:filters="filters"
						@change="set_filters"
					/>
					<Button
						v-if="!Number(widget.hide_refresh)"
						size="sm"
						variant="ghost"
						icon="lucide-refresh-cw"
						:label="__('Refresh List')"
						@click="load"
					/>
					<Button
						v-if="can_create && !Number(widget.hide_new)"
						size="sm"
						variant="ghost"
						icon="lucide-plus"
						:label="__('Add New') + ' ' + __(doctype)"
						@click="add_new"
					/>
				</div>
			</template>
			<template #empty>
				<span class="text-p-sm text-ink-gray-5">{{ __("No Data...") }}</span>
			</template>
			<div
				ref="list"
				class="-mx-2 flex flex-col overflow-hidden"
				:class="{ 'min-h-16': rows?.length === 0 }"
			>
				<ItemListRow
					v-for="doc in visible"
					:key="doc.name"
					as="button"
					type="button"
					class="text-left hover:bg-surface-gray-2"
					@click="open(doc, $event)"
				>
					<span class="block truncate text-ink-gray-8">{{
						text(doc[title_field])
					}}</span>
					<span class="block truncate text-sm text-ink-gray-5">
						{{ subtitle(doc) }}
					</span>
					<template v-if="indicator(doc) && !one_status" #suffix>
						<Badge
							:label="indicator(doc)[0]"
							:theme="badge_theme(indicator(doc)[1])"
						/>
					</template>
				</ItemListRow>
			</div>
			<template v-if="!Number(widget.hide_view_list)" #legend>
				<Button class="self-start" size="sm" :label="__('View List')" @click="open_list" />
			</template>
		</ChartContainer>
	</ChartCard>
</template>
