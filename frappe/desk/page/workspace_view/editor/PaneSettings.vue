<script setup>
import { onMounted, ref } from "vue";
import { Select, Switch, TextInput, Textarea } from "frappe-ui";

// What the pencil is on, with no block selected: the page's own fields, and the layout's name,
// condition and, for a developer, the app it ships with.
const props = defineProps({
	page: { type: Object, default: null },
	page_fields: { type: Array, default: () => [] },
	layout: { type: Object, default: null },
	layout_fields: { type: Array, default: () => [] },
});

const emit = defineEmits(["change"]);
const __ = window.__;
const frappe = window.frappe;

// all a condition can read, as the server's condition namespace has it
const NAMESPACE = [
	"frappe.get_roles()",
	"frappe.get_installed_apps()",
	"frappe.get_system_settings(key)",
	"frappe.db.get_single_value(doctype, field)",
	"frappe.db.exists(doctype, filters)",
	"frappe.db.get_value(doctype, name, field)",
	"frappe.session.user",
	"frappe.defaults.get_user_default(key)",
];

const modules = ref([]);
onMounted(async () => {
	const wants_module = [...props.page_fields, ...props.layout_fields].includes("module");
	if (wants_module)
		modules.value = frappe.ui.workspace_module_options(
			await frappe.ui.get_assignable_modules()
		);
});

function set(target, field, value) {
	target[field] = value;
	emit("change");
}

const has = (fields, field) => fields.includes(field);
</script>

<template>
	<section class="flex flex-col gap-4 border-t border-outline-gray-2 p-5">
		<template v-if="layout && layout_fields.length">
			<span class="text-base font-medium text-ink-gray-8">{{ __("Layout") }}</span>
			<TextInput
				v-if="has(layout_fields, 'layout_name')"
				:placeholder="__('Name')"
				:aria-label="__('Name')"
				:model-value="layout.layout_name"
				@update:model-value="(value) => set(layout, 'layout_name', value)"
			/>
			<div v-if="has(layout_fields, 'condition')" class="flex flex-col gap-1.5">
				<span class="text-sm text-ink-gray-6">{{ __("Show when") }}</span>
				<Textarea
					class="font-mono"
					:placeholder="'&quot;Accounts User&quot; in frappe.get_roles()'"
					:aria-label="__('Show when')"
					:model-value="layout.condition"
					@update:model-value="(value) => set(layout, 'condition', value)"
				/>
				<p class="text-p-sm text-ink-gray-5">
					{{ __("Blank shows it to everyone. A condition can read:") }}
				</p>
				<ul class="font-mono text-xs text-ink-gray-5">
					<li v-for="name in NAMESPACE" :key="name">{{ name }}</li>
				</ul>
			</div>
			<Select
				v-if="has(layout_fields, 'module')"
				:aria-label="__('Module')"
				:options="[{ label: __('This site'), value: '' }, ...modules]"
				:model-value="layout.module || ''"
				@update:model-value="(value) => set(layout, 'module', value)"
			/>
		</template>

		<template v-if="page && page_fields.length">
			<span class="text-base font-medium text-ink-gray-8">{{ __("Page") }}</span>
			<TextInput
				v-if="has(page_fields, 'title')"
				:placeholder="__('Title')"
				:aria-label="__('Title')"
				:model-value="page.title"
				@update:model-value="(value) => set(page, 'title', value)"
			/>
			<TextInput
				v-if="has(page_fields, 'icon')"
				:placeholder="__('Icon')"
				:aria-label="__('Icon')"
				:model-value="page.icon"
				@update:model-value="(value) => set(page, 'icon', value)"
			/>
			<Select
				v-if="has(page_fields, 'module')"
				:aria-label="__('Module')"
				:options="modules"
				:model-value="page.module"
				@update:model-value="(value) => set(page, 'module', value)"
			/>
			<label v-if="has(page_fields, 'hide_custom')" class="flex items-center gap-2">
				<Switch
					:model-value="!page.hide_custom"
					@update:model-value="(value) => set(page, 'hide_custom', value ? 0 : 1)"
				/>
				<span class="text-sm text-ink-gray-7">{{
					__("Show custom documents and reports")
				}}</span>
			</label>
		</template>
	</section>
</template>
