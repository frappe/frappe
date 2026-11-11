<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { Button, Select, Switch, TabButtons, TextInput, Textarea } from "frappe-ui";
import { Link } from "@framework/ui";
import InlineFilter from "./InlineFilter.vue";
import { block_size } from "../grid.js";
import { attempt } from "../api.js";
import { filter_rows } from "../filters.js";
import {
	HEIGHTS,
	TEXT_SIZES,
	has_heights,
	height_of,
	set_height,
	set_text,
	sizes_of,
	text_of,
	text_size,
} from "./editor.js";
import RecordForm from "./RecordForm.vue";
import { RECORDS, blank_record, can_edit, load_record } from "./records.js";

// The selected block's fields, its size and its removal. Every change applies to the canvas live.
const props = defineProps({
	block: { type: Object, required: true },
	widget: { type: Object, default: null },
});

const emit = defineEmits(["change", "resize", "remove", "close", "form"]);
const __ = window.__;

const TITLES = {
	number_card: __("Number Card"),
	chart: __("Chart"),
	shortcut: __("Shortcut"),
	card: __("Card"),
	quick_list: __("Quick List"),
	onboarding: __("Onboarding"),
	custom_block: __("Custom Block"),
	header: __("Text"),
	paragraph: __("Text"),
	spacer: __("Section break"),
};

const LINK_TYPES = ["DocType", "Report", "Page"];

// A slimmed copy of desk's widget dialog: `link` names a doctype, `options` makes a select,
// `inverse_switch` is a switch that is on while its check is off, and
// `when` hides a field the widget's other values make moot.
const FIELDS = {
	shortcut: [
		{ field: "type", label: "Type", options: [...LINK_TYPES, "URL"] },
		{ field: "link_to", label: "Link To", link: (w) => w.type, when: (w) => w.type !== "URL" },
		{ field: "url", label: "URL", when: (w) => w.type === "URL" },
		{
			field: "doc_view",
			label: "DocType View",
			options: [
				"",
				"List",
				"Report Builder",
				"Dashboard",
				"Tree",
				"New",
				"Calendar",
				"Kanban",
				"Image",
			],
			when: (w) => w.type === "DocType",
		},
		{
			field: "color",
			label: "Color",
			options: ["", "Grey", "Green", "Red", "Orange", "Pink", "Yellow", "Blue", "Cyan"],
		},
		{ field: "format", label: "Format", placeholder: "{} Open" },
		{
			field: "stats_filter",
			label: "Filter",
			filter: true,
			filter_doctype: (w) => w.link_to,
			when: (w) =>
				w.type === "DocType" &&
				w.link_to &&
				w.doc_view !== "New" &&
				!window.frappe.boot.single_types.includes(w.link_to),
		},
	],
	card: [{ field: "description", label: "Description", textarea: true }],
	quick_list: [
		{ field: "document_type", label: "DocType", link: "DocType" },
		{
			field: "order_by",
			label: "Order",
			options: (w) => order_options(w.document_type),
			when: (w) => w.document_type,
		},
		{ field: "hide_filter", label: "Filter", inverse_switch: true },
		{ field: "hide_refresh", label: "Refresh", inverse_switch: true },
		{ field: "hide_new", label: "Add new", inverse_switch: true },
		{ field: "hide_view_list", label: "View List", inverse_switch: true },
	],
};

const SORTABLE = ["Date", "Datetime", "Int", "Float", "Currency", "Duration", "Rating"];

// newest first, the session user's latest action, or a date or number field either way
function order_options(doctype) {
	const options = [
		{ label: __("Newest first"), value: "" },
		{ label: __("My recent activity"), value: "my_activity" },
	];
	for (const df of window.frappe.get_meta(doctype)?.fields || []) {
		if (!SORTABLE.includes(df.fieldtype)) continue;
		const label = __(df.label);
		options.push(
			{ label: __("{0}, lowest first", [label]), value: `${df.fieldname} asc` },
			{ label: __("{0}, highest first", [label]), value: `${df.fieldname} desc` }
		);
	}
	return options;
}

function options_of(field) {
	if (typeof field.options === "function") return field.options(props.widget);
	return field.options.map((value) => ({ label: __(value), value }));
}

const height_options = HEIGHTS.map((name) => ({ label: __(name), value: name }));
const height = computed({
	get: () => height_of(props.block),
	set: (value) => set_height(props.block, value),
});

const is_text = computed(() => ["header", "paragraph"].includes(props.block.type));
const record_spec = computed(() => RECORDS[props.block.type]);
const record = computed(() => (record_spec.value ? props.widget?.record : null));
const editable = computed(() => record.value && can_edit(props.block.type, record.value));
const linked = computed(() => record_spec.value && props.widget?.[record_spec.value.link]);
const can_create = computed(
	() => record_spec.value && window.frappe.model.can_create(record_spec.value.doctype)
);

// A record's whole form takes the pane, and the editor hides what it would otherwise show.
const form_open = ref(false);
watch(form_open, (open) => emit("form", open));
onBeforeUnmount(() => emit("form", false));
const fields = computed(() =>
	(FIELDS[props.block.type] || []).filter((f) => !f.when || f.when(props.widget))
);

watch(
	() => record_spec.value && !props.widget?.record && props.widget?.[record_spec.value.link],
	(name) => {
		if (!name) return;
		attempt(async () => {
			props.widget.record = await load_record(props.block.type, name);
		});
	},
	{ immediate: true }
);

const size_options = computed(() =>
	sizes_of(props.block.type).map((name) => ({ label: __(name), value: name }))
);
const size = computed({
	get: () => block_size(props.block).name,
	set: (preset) => emit("resize", preset),
});

const text = ref(is_text.value ? text_of(props.block) : "");
const text_options = Object.keys(TEXT_SIZES).map((name) => ({ label: __(name), value: name }));
const current_text_size = computed({
	get: () => text_size(props.block),
	set: (value) => set_text(props.block, text.value, value),
});

function set_text_value(value) {
	text.value = value;
	set_text(props.block, value, text_size(props.block));
}

function set(field, value) {
	props.widget[field.field] = value;
	if (field.field === "label") props.widget.renamed = true;
	emit("change");
}

function link_doctype(field) {
	return typeof field.link === "function" ? field.link(props.widget) : field.link;
}

// Picking a record or making one opens its form.
function pick(name) {
	if (!name) return;
	if (name !== linked.value && props.block.type === "onboarding") {
		props.block.data.onboarding_name = name;
	} else if (name !== linked.value) {
		props.widget.record = null;
		props.widget.record_changed = false;
		set({ field: record_spec.value.link }, name);
	}
	form_open.value = true;
}

// A new record is named after the widget, so a typed name becomes its label.
function create(query) {
	const { link } = record_spec.value;
	props.widget[link] = null;
	props.widget.record = blank_record(props.block.type);
	props.widget.record_changed = true;
	if (query && props.block.type === "onboarding") {
		props.widget.record.title = props.widget.title = query;
	} else if (query) {
		set({ field: "label" }, query);
	}
	emit("change");
	form_open.value = true;
}

function open_full_form() {
	window.open(window.frappe.utils.get_form_link(record_spec.value.doctype, record.value.name));
}

function add_link() {
	props.widget.links.push({ type: "Link", link_type: "DocType", link_to: "", label: "" });
	emit("change");
}

function remove_link(index) {
	props.widget.links.splice(index, 1);
	emit("change");
}
</script>

<template>
	<section class="flex flex-col">
		<header
			class="sticky top-0 z-10 flex items-center gap-1 border-b border-outline-gray-1 bg-surface-base py-2.5 pr-3 pl-5"
		>
			<Button
				v-if="form_open"
				size="sm"
				variant="ghost"
				icon="lucide-arrow-left"
				:label="__('Back')"
				@click="form_open = false"
			/>
			<span class="min-w-0 flex-1 truncate text-base font-medium text-ink-gray-8">
				<template v-if="form_open">
					{{ linked || __("New {0}", [__(record_spec.doctype)]) }}
				</template>
				<template v-else>{{ TITLES[block.type] || __("Block") }}</template>
			</span>
			<Button
				size="sm"
				variant="ghost"
				icon="lucide-trash-2"
				:label="__('Remove block')"
				@click="emit('remove')"
			/>
			<Button
				size="sm"
				variant="ghost"
				icon="lucide-x"
				:label="__('Close')"
				@click="emit('close')"
			/>
		</header>

		<div class="grid grid-cols-[5.5rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2 p-5">
			<template v-if="is_text">
				<span class="self-start pt-1.5 text-sm text-ink-gray-6">{{ __("Text") }}</span>
				<Textarea
					:aria-label="__('Text')"
					:model-value="text"
					@update:model-value="set_text_value"
				/>
				<span class="text-sm text-ink-gray-6">{{ __("Text size") }}</span>
				<TabButtons v-model="current_text_size" :options="text_options" />
			</template>

			<p v-if="block.type === 'spacer'" class="col-span-2 text-p-sm text-ink-gray-5">
				{{
					__(
						"Leaves a gap here. Blocks after it start on a new row, below everything above."
					)
				}}
			</p>

			<template v-if="widget">
				<template v-if="form_open">
					<p
						v-if="!editable || record.name"
						class="col-span-2 text-p-sm text-ink-gray-5"
					>
						<template v-if="!editable && record.is_standard">
							{{ __("This one ships with an app, so it can't be changed here.") }}
						</template>
						<template v-else-if="!editable">
							{{ __("You don't have permission to change this one.") }}
						</template>
						<template v-else>
							{{ __("Saving changes it everywhere it is used.") }}
						</template>
					</p>
					<div v-if="record" class="col-span-2 min-w-0 [&_pre]:overflow-x-auto">
						<RecordForm
							:key="linked || block.id"
							:type="block.type"
							:widget="widget"
							:locked="!editable"
							@change="emit('change')"
						/>
					</div>
					<Button
						v-if="record?.name"
						class="col-span-2 justify-self-start"
						variant="ghost"
						icon-right="lucide-arrow-up-right"
						:label="__('Open full form')"
						@click="open_full_form"
					/>
				</template>

				<template v-else>
					<template v-if="block.type !== 'onboarding'">
						<span class="text-sm text-ink-gray-6">{{ __("Label") }}</span>
						<TextInput
							:aria-label="__('Label')"
							:model-value="widget.label"
							@update:model-value="(value) => set({ field: 'label' }, value)"
						/>
					</template>
					<template v-for="field in fields" :key="field.field">
						<div v-if="field.filter" class="col-span-2 flex flex-col gap-1.5 pt-2">
							<span class="text-sm text-ink-gray-6">{{ __(field.label) }}</span>
							<InlineFilter
								:key="field.filter_doctype(widget)"
								:doctype="field.filter_doctype(widget)"
								:filters="
									filter_rows(widget[field.field], field.filter_doctype(widget))
								"
								@change="(rows) => set(field, JSON.stringify(rows))"
							/>
						</div>
						<Switch
							v-else-if="field.inverse_switch"
							class="col-span-2"
							:label="__(field.label)"
							:model-value="!Number(widget[field.field])"
							@update:model-value="(on) => set(field, on ? 0 : 1)"
						/>
						<template v-else>
							<span
								class="text-sm text-ink-gray-6"
								:class="field.textarea && 'self-start pt-1.5'"
							>
								{{ __(field.label) }}
							</span>
							<Link
								v-if="field.link"
								:key="link_doctype(field)"
								:aria-label="__(field.label)"
								:doctype="link_doctype(field)"
								:model-value="widget[field.field]"
								@update:model-value="(value) => set(field, value)"
							/>
							<Select
								v-else-if="field.options"
								:aria-label="__(field.label)"
								:options="options_of(field)"
								:model-value="widget[field.field] || ''"
								@update:model-value="(value) => set(field, value)"
							/>
							<Textarea
								v-else-if="field.textarea"
								:aria-label="__(field.label)"
								:model-value="widget[field.field]"
								@update:model-value="(value) => set(field, value)"
							/>
							<TextInput
								v-else
								:aria-label="__(field.label)"
								:placeholder="field.placeholder"
								:model-value="widget[field.field]"
								@update:model-value="(value) => set(field, value)"
							/>
						</template>
					</template>

					<template v-if="record_spec">
						<span class="text-sm text-ink-gray-6">{{ __(record_spec.label) }}</span>
						<Link
							:aria-label="__(record_spec.label)"
							:doctype="record_spec.doctype"
							:model-value="linked"
							:creatable="can_create"
							:placeholder="can_create ? __('Search or create') : __('Search')"
							@update:model-value="pick"
							@create="create"
						>
							<template v-if="record" #suffix>
								<button
									type="button"
									class="grid size-4 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
									:aria-label="__('Edit')"
									:title="__('Edit')"
									@click.stop="form_open = true"
									@pointerdown.stop
								>
									<span class="lucide-square-pen size-3.5" aria-hidden="true" />
								</button>
							</template>
						</Link>
						<p
							v-if="!can_create && !linked"
							class="col-span-2 text-p-sm text-ink-gray-5"
						>
							{{
								__(
									"You don't have permission to create one. Pick an existing one."
								)
							}}
						</p>
					</template>
					<div v-if="block.type === 'card'" class="col-span-2 flex flex-col gap-2 pt-2">
						<span class="text-sm text-ink-gray-6">{{ __("Links") }}</span>
						<div
							v-for="(link, index) in widget.links"
							:key="index"
							class="flex flex-col gap-1.5 rounded-4 border border-outline-gray-1 p-2"
						>
							<Select
								:options="LINK_TYPES.map((value) => ({ label: __(value), value }))"
								:model-value="link.link_type"
								@update:model-value="
									(value) => ((link.link_type = value), emit('change'))
								"
							/>
							<Link
								:key="link.link_type"
								:doctype="link.link_type"
								:model-value="link.link_to"
								@update:model-value="
									(value) => ((link.link_to = value), emit('change'))
								"
							/>
							<TextInput
								:placeholder="__('Label')"
								:model-value="link.label"
								@update:model-value="
									(value) => ((link.label = value), emit('change'))
								"
							/>
							<Button
								class="self-end"
								size="sm"
								variant="ghost"
								icon="lucide-trash-2"
								:label="__('Remove link')"
								@click="remove_link(index)"
							/>
						</div>
						<Button
							class="self-start"
							icon-left="lucide-plus"
							:label="__('Add link')"
							@click="add_link"
						/>
					</div>
				</template>
			</template>

			<template v-if="size_options.length > 1 && !form_open">
				<span class="text-sm text-ink-gray-6">{{ __("Size") }}</span>
				<TabButtons v-model="size" :options="size_options" />
			</template>
			<template v-if="has_heights(block) && !form_open">
				<span class="text-sm text-ink-gray-6">{{ __("Height") }}</span>
				<TabButtons v-model="height" :options="height_options" />
			</template>
		</div>
	</section>
</template>
