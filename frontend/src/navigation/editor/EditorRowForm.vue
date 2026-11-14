<!-- The right pane while a new row is being added: the type's fields and a subtle "Add row". -->
<template>
	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 pt-5" data-editor-form>
		<EditorPaneHeading
			icon="lucide-plus"
			:title="__('Add {0}', [typeLabel])"
			:origin="__('A new row')"
		/>
		<div class="flex flex-col gap-3">
			<Select
				v-if="type === 'DocType'"
				v-model="values.doctype"
				:label="__('DocType')"
				:options="doctypes"
				data-field="doctype"
			/>
			<template v-if="type === 'Link'">
				<FormControl
					v-model="values.url"
					type="text"
					:label="__('Link')"
					placeholder="/app/todo"
					data-field="url"
				/>
				<p class="text-xs text-ink-gray-5" data-link-note>{{ linkNote }}</p>
			</template>
			<FormControl
				v-if="type !== 'DocType'"
				v-model="values.label"
				type="text"
				:label="__('Label')"
				data-field="label"
			/>
			<template v-if="type === 'Section'">
				<Checkbox v-model="values.collapsible" :label="__('Can collapse')" />
				<Checkbox
					v-model="values.keepClosed"
					:disabled="!values.collapsible"
					:label="__('Starts closed')"
				/>
			</template>
			<p v-if="problem" class="text-xs text-ink-red-4" data-refusal>{{ problem }}</p>
		</div>
		<div
			class="mt-auto flex h-[49px] shrink-0 items-center justify-end border-t border-outline-gray-1"
		>
			<Button variant="subtle" :label="__('Add row')" data-add-row @click="submit" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, reactive, ref } from "vue";
import { Button, Checkbox, FormControl, Select } from "frappe-ui";
import type { Addresses } from "@/addresses";
import { __ } from "@/i18n";
import { type AddValues, buildRow, missing } from "./addTypes";
import type { EditorRow } from "./draft";
import EditorPaneHeading from "./EditorPaneHeading.vue";

const props = defineProps<{ type: string; typeLabel: string; refusal: string | null }>();
const emit = defineEmits<{ add: [row: Omit<EditorRow, "key">] }>();

const doctypes = [
	{ label: __("Pick a DocType"), value: "" },
	...inject<Addresses>("addresses")!
		.doctypes()
		.map((name) => ({ label: name, value: name })),
];
const values = reactive<AddValues>({
	doctype: "",
	url: "",
	label: "",
	collapsible: false,
	keepClosed: false,
});
const gap = ref<string | null>(null);
const problem = computed(() => props.refusal ?? gap.value);

const linkNote = computed(() => {
	const url = values.url.trim();
	if (!url) return __("This site: write it as a /path so it opens in place.");
	if (url.startsWith("/")) return __("Internal: opens here, in place.");
	if (/^https?:\/\//i.test(url))
		return __("External: opens in a new tab, marked with an arrow.");
	return __("Only /paths and http(s) links can be added.");
});

function submit() {
	const lacking = missing(props.type, values);
	gap.value = lacking?.message ?? null;
	if (!lacking) emit("add", buildRow(props.type, "", values));
}
</script>
