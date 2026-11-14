<!-- The right pane while a new row is being added: the type's fields and a subtle "Add row". -->
<template>
	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 pt-5" data-editor-form>
		<EditorPaneHeading
			icon="plus"
			:title="__('Add {0}', [typeLabel])"
			:origin="__('A new row')"
		/>
		<div class="flex flex-col gap-3">
			<div v-if="type === 'DocType' || type === 'Record'" class="flex flex-col gap-1.5">
				<label class="text-xs text-ink-gray-5">{{ __("DocType") }}</label>
				<Combobox
					v-model="doctype"
					:options="doctypes"
					:placeholder="__('Pick a DocType')"
					data-field="doctype"
				/>
			</div>
			<div v-if="type === 'Record' && values.doctype" class="flex flex-col gap-1.5">
				<label class="text-xs text-ink-gray-5">{{ __("Record") }}</label>
				<Link
					:key="values.doctype"
					v-model="values.name"
					:doctype="values.doctype"
					data-field="name"
				/>
			</div>
			<Select
				v-if="type === 'Page'"
				v-model="values.page"
				:label="__('Page')"
				:options="pages"
				data-field="page"
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
import { Button, Checkbox, Combobox, FormControl, Select } from "frappe-ui";
import { Link } from "@framework/ui/Link";
import { useRouter } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { pages as contributedPages } from "@/contributions/registry";
import { __ } from "@/i18n";
import { type AddValues, buildRow, missing, startValues } from "./addTypes";
import type { EditorRow } from "./draft";
import EditorPaneHeading from "./EditorPaneHeading.vue";

const props = defineProps<{
	type: string;
	typeLabel: string;
	refusal: string | null;
	start?: Partial<EditorRow>;
}>();
const emit = defineEmits<{ add: [row: Omit<EditorRow, "key">] }>();

const boot = inject<Boot>("boot")!;
const router = useRouter();
const doctypes = inject<Addresses>("addresses")!
	.doctypes()
	.map((name) => ({ label: name, value: name }));
// Only the pages this app's router serves: a slug it drops (a clash) would open the not-found page.
const pages = [
	{ label: __("Pick a page"), value: "" },
	...contributedPages
		.filter(
			(page) => router.hasRoute(`page:${page.app}:${page.slug}`) && page.app === boot.app
		)
		.map((page) => ({ label: page.title ?? page.slug, value: page.slug })),
];
const values = reactive<AddValues>(startValues(props.start));
// Another DocType makes the picked record meaningless.
const doctype = computed({
	get: () => values.doctype || null,
	set: (picked: string | null) => {
		values.doctype = picked ?? "";
		values.name = "";
	},
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
	if (lacking) return;
	// A page with no label of its own takes its title, not its slug.
	const title = pages.find((page) => page.value === values.page)?.label;
	const label = props.type === "Page" && !values.label.trim() && title ? title : values.label;
	emit("add", buildRow(props.type, "", { ...values, label }));
}
</script>
