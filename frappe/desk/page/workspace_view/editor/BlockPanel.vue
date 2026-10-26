<script setup>
import { computed, ref } from "vue";
import { Button, Select, TabButtons, TextInput, Textarea } from "frappe-ui";
import { Link } from "@framework/ui";
import { block_size } from "../grid.js";
import { TEXT_SIZES, set_text, sizes_of, text_of, text_size } from "./editor.js";

// The selected block's fields, its size and its removal. Every change applies to the canvas live.
const props = defineProps({
	block: { type: Object, required: true },
	widget: { type: Object, default: null },
});

const emit = defineEmits(["change", "resize", "remove", "close"]);
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
};

const LINK_TYPES = ["DocType", "Report", "Page"];

// A slimmed copy of desk's widget dialog: `link` names a doctype, `options` makes a select, and
// `when` hides a field the widget's other values make moot.
const FIELDS = {
	number_card: [{ field: "number_card_name", label: "Number Card", link: "Number Card" }],
	chart: [{ field: "chart_name", label: "Dashboard Chart", link: "Dashboard Chart" }],
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
	],
	custom_block: [
		{ field: "custom_block_name", label: "Custom HTML Block", link: "Custom HTML Block" },
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

const is_text = computed(() => ["header", "paragraph"].includes(props.block.type));
const fields = computed(() =>
	(FIELDS[props.block.type] || []).filter((f) => !f.when || f.when(props.widget))
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
	props.widget[field] = value;
	if (field === "label") props.widget.renamed = true;
	emit("change");
}

function link_doctype(field) {
	return typeof field.link === "function" ? field.link(props.widget) : field.link;
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
	<aside
		class="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-l border-outline-gray-1 p-4"
	>
		<div class="flex items-center justify-between">
			<span class="text-base font-medium text-ink-gray-8">
				{{ TITLES[block.type] || __("Block") }}
			</span>
			<Button
				size="sm"
				variant="ghost"
				icon="lucide-x"
				:label="__('Close')"
				@click="emit('close')"
			/>
		</div>

		<template v-if="is_text">
			<Textarea
				:label="__('Text')"
				:model-value="text"
				@update:model-value="set_text_value"
			/>
			<div class="flex flex-col gap-1.5">
				<span class="text-sm text-ink-gray-5">{{ __("Text size") }}</span>
				<TabButtons v-model="current_text_size" :options="text_options" />
			</div>
		</template>

		<Link
			v-if="block.type === 'onboarding'"
			:label="__('Module Onboarding')"
			doctype="Module Onboarding"
			:model-value="block.data.onboarding_name"
			@update:model-value="(value) => (block.data.onboarding_name = value)"
		/>

		<template v-if="widget">
			<template v-for="field in fields" :key="field.field">
				<Link
					v-if="field.link"
					:key="link_doctype(field)"
					:label="__(field.label)"
					:doctype="link_doctype(field)"
					:model-value="widget[field.field]"
					@update:model-value="(value) => set(field.field, value)"
				/>
				<Select
					v-else-if="field.options"
					:label="__(field.label)"
					:options="options_of(field)"
					:model-value="widget[field.field] || ''"
					@update:model-value="(value) => set(field.field, value)"
				/>
				<Textarea
					v-else-if="field.textarea"
					:label="__(field.label)"
					:model-value="widget[field.field]"
					@update:model-value="(value) => set(field.field, value)"
				/>
				<TextInput
					v-else
					:label="__(field.label)"
					:placeholder="field.placeholder"
					:model-value="widget[field.field]"
					@update:model-value="(value) => set(field.field, value)"
				/>
			</template>
			<TextInput
				:label="__('Label')"
				:model-value="widget.label"
				@update:model-value="(value) => set('label', value)"
			/>

			<div v-if="block.type === 'card'" class="flex flex-col gap-2">
				<span class="text-sm text-ink-gray-5">{{ __("Links") }}</span>
				<div
					v-for="(link, index) in widget.links"
					:key="index"
					class="flex flex-col gap-1.5 rounded-4 border border-outline-gray-1 p-2"
				>
					<Select
						:options="LINK_TYPES.map((value) => ({ label: __(value), value }))"
						:model-value="link.link_type"
						@update:model-value="(value) => ((link.link_type = value), emit('change'))"
					/>
					<Link
						:key="link.link_type"
						:doctype="link.link_type"
						:model-value="link.link_to"
						@update:model-value="(value) => ((link.link_to = value), emit('change'))"
					/>
					<TextInput
						:placeholder="__('Label')"
						:model-value="link.label"
						@update:model-value="(value) => ((link.label = value), emit('change'))"
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

		<div v-if="size_options.length > 1" class="flex flex-col gap-1.5">
			<span class="text-sm text-ink-gray-5">{{ __("Size") }}</span>
			<TabButtons v-model="size" :options="size_options" />
		</div>
		<Button
			class="self-start"
			theme="red"
			icon-left="lucide-trash-2"
			:label="__('Remove block')"
			@click="emit('remove')"
		/>
	</aside>
</template>
