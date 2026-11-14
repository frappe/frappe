<!-- The right pane while a new row is being added: the type's fields and a subtle "Add row". -->
<template>
	<form
		class="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 pt-5"
		novalidate
		data-editor-form
		@submit.prevent="submit"
	>
		<EditorPaneHeading
			icon="plus"
			:title="__('Add {0}', [typeLabel])"
			:origin="__('A new row')"
		/>
		<div ref="fields" class="flex flex-col gap-3">
			<Combobox
				v-if="type === 'DocType' || type === 'Record'"
				v-model="doctype"
				:label="__('DocType')"
				:options="doctypes"
				:placeholder="__('Pick a DocType')"
				:error="errorOf('doctype')"
				data-field="doctype"
			/>
			<Link
				v-if="type === 'Record' && values.doctype"
				:key="values.doctype"
				v-model="values.name"
				:label="__('Record')"
				:doctype="values.doctype"
				:error="errorOf('name')"
				data-field="name"
			/>
			<Select
				v-if="type === 'Page'"
				v-model="values.page"
				:label="__('Page')"
				:options="pages"
				:placeholder="__('Pick a page')"
				:error="errorOf('page')"
				data-field="page"
			/>
			<FormControl
				v-if="type === 'Link'"
				v-model="values.url"
				type="text"
				:label="__('Link')"
				placeholder="/app/todo"
				:description="linkNote"
				:error="errorOf('url')"
				data-field="url"
			/>
			<FormControl
				v-if="type !== 'DocType'"
				v-model="values.label"
				type="text"
				:label="__('Label')"
				:error="errorOf('label')"
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
			<p v-if="refusal" class="text-p-sm text-ink-red-7" role="alert" data-refusal>
				{{ refusal }}
			</p>
		</div>
		<div
			class="mt-auto flex h-[49px] shrink-0 items-center justify-end border-t border-outline-gray-1"
		>
			<Button variant="subtle" type="submit" :label="__('Add row')" data-add-row />
		</div>
	</form>
</template>

<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { Button, Checkbox, Combobox, FormControl, Select } from "frappe-ui";
import { Link } from "@framework/ui/Link";
import { useRouter } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { type AddValues, buildRow, isOwnUrl, missing, servedPages, startValues } from "./addTypes";
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
const pages = servedPages((name) => router.hasRoute(name), boot.app);
const values = reactive<AddValues>(startValues(props.start));
// Another DocType makes the picked record meaningless.
const doctype = computed({
	get: () => values.doctype || null,
	set: (picked: string | null) => {
		values.doctype = picked ?? "";
		values.name = "";
	},
});
// What the form lacks, shown under the field that lacks it; the editor's own refusal shows under the form.
const gap = ref<{ field: keyof AddValues; message: string } | null>(null);
const errorOf = (field: keyof AddValues) =>
	gap.value?.field === field ? gap.value.message : undefined;
// The error goes as soon as its field changes.
watch(
	() => ({ ...values }),
	(now, before) => {
		if (gap.value && now[gap.value.field] !== before[gap.value.field]) gap.value = null;
	}
);

// The add menu hands focus back to its button once its close has played out, after the form is up: the form takes it back once.
const fields = ref<HTMLElement | null>(null);
const firstField = () => fields.value?.querySelector<HTMLElement>("input, button, select");
function takeBack(event: FocusEvent) {
	const target = event.target as HTMLElement;
	if (fields.value?.contains(target)) return;
	document.removeEventListener("focusin", takeBack);
	if (target.closest("[data-add]")) firstField()?.focus();
}
onMounted(() => {
	firstField()?.focus();
	document.addEventListener("focusin", takeBack);
});
onBeforeUnmount(() => document.removeEventListener("focusin", takeBack));

const linkNote = computed(() => {
	const url = values.url.trim();
	if (!url) return __("This site: write it as a /path so it opens in place.");
	if (!isOwnUrl(url)) return __("Only /paths and http(s) links can be added.");
	if (url.startsWith("/")) return __("Internal: opens here, in place.");
	return __("External: opens in a new tab, marked with an arrow.");
});

function submit() {
	const lacking = missing(props.type, values);
	gap.value = lacking;
	if (lacking) return;
	// A page with no label of its own takes its title, not its slug.
	const title = pages.find((page) => page.value === values.page)?.label;
	const label = props.type === "Page" && !values.label.trim() && title ? title : values.label;
	emit("add", buildRow(props.type, { ...values, label }));
}
</script>
