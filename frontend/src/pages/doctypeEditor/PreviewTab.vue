<!-- The Preview tab: the record page's own FormLayout on a copy of one record. It never writes:
     typing changes only the copy, and `refuseWrites` drops field events, uploads and Create. -->
<template>
	<div class="mx-auto w-full max-w-3xl py-4" data-editor-preview>
		<div class="mb-1 flex items-center gap-2 px-5">
			<Combobox
				:model-value="record ?? EMPTY"
				:options="options"
				:placeholder="__('Search records')"
				@update:model-value="
					emit('pick', $event && $event !== EMPTY ? String($event) : null)
				"
			>
				<template #trigger="{ open }">
					<button
						type="button"
						class="-ml-1 flex min-w-0 max-w-[320px] items-center gap-1 rounded-4 px-1 py-1 text-p-sm text-ink-gray-5"
						:class="open ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2'"
						data-preview-record
					>
						<span class="shrink-0">{{ __("Previewing") }}</span>
						<span class="min-w-0 truncate text-ink-gray-8">{{
							record ?? __("an empty form")
						}}</span>
						<span v-if="title" class="min-w-0 truncate">{{ title }}</span>
						<span class="lucide-chevron-down size-4 shrink-0" aria-hidden="true" />
					</button>
				</template>
			</Combobox>
			<span v-if="loading" class="text-p-sm text-ink-gray-5">{{ __("Loading…") }}</span>
			<span class="ml-auto shrink-0 text-p-sm text-ink-gray-5">{{
				__("Changes here are not saved.")
			}}</span>
		</div>
		<div v-if="failure" class="flex flex-col items-start gap-2 px-5 py-4" data-preview-failure>
			<ErrorMessage :message="asErrorHtml(failure.message)" />
			<Button :label="__('Try again')" @click="failure.retry" />
		</div>
		<FormSkeleton
			v-else-if="details.loading.value"
			class="px-5 py-4"
			:columns="2"
			:fields="6"
		/>
		<FormLayout
			v-else
			:key="record ?? EMPTY"
			v-model:doc="doc"
			v-model:tab="tab"
			:layout="details.layout.value"
			:doctype="doctype"
			:class="FORM_CLASSES"
		>
			<template #tab-label="{ label, unlabelled }">
				<span :class="{ 'text-ink-gray-4': unlabelled }">{{ label }}</span>
			</template>
		</FormLayout>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Button, Combobox, ErrorMessage } from "frappe-ui";
import { getDocument } from "@framework/ui/api";
import { FormLayout } from "@framework/ui/FormLayout";
import { __ } from "@/i18n";
import { FORM_CLASSES } from "@/pages/record/formClasses";
import FormSkeleton from "@/pages/record/skeletons/FormSkeleton.vue";
import { errorMessage } from "@/recordPage/errorMessage";
import { asErrorHtml } from "./asErrorHtml";
import { useFormLayout } from "@/recordPage/formLayoutSource/useFormLayout";
import { refuseWrites } from "./previewRefusals";

const props = defineProps<{
	doctype: string;
	record: string | null;
	latest: string[];
	titleField: string;
}>();
const emit = defineEmits<{ pick: [name: string | null] }>();

const EMPTY = "__empty__";
refuseWrites();

const doc = ref<Record<string, any>>({});
const tab = ref("");
const loading = ref(false);
const recordError = ref<unknown>(null);
const details = useFormLayout({
	doctype: () => props.doctype,
	type: "Details",
	doc,
	fallback: "meta",
});

// The record's title, once it loads, after its name; a record titled by its ID shows no second word.
const title = computed(() => {
	const value = props.titleField && props.record ? doc.value[props.titleField] : null;
	return value && value !== props.record ? String(value) : "";
});

const options = computed(() => [
	{ label: __("Empty form"), value: EMPTY },
	...props.latest.map((name) => ({ label: name, value: name })),
]);

// A failed read keeps the picked record: the page says why, and Try again reads it once more.
const failure = computed(() => {
	if (details.error.value) {
		const reason = errorMessage(details.error.value);
		return { message: __("Could not load the layout. {0}", [reason]), retry: details.reload };
	}
	if (!recordError.value || !props.record) return null;
	const name = props.record;
	const reason = errorMessage(recordError.value);
	return { message: __("Could not load {0}. {1}", [name, reason]), retry: () => load(name) };
});

async function load(name: string) {
	loading.value = true;
	recordError.value = null;
	try {
		const { data } = await getDocument(props.doctype, name);
		if (props.record === name) doc.value = structuredClone(data);
	} catch (error) {
		if (props.record === name) recordError.value = error;
	} finally {
		loading.value = false;
	}
}

watch(
	() => props.record,
	(name) => {
		recordError.value = null;
		if (!name) return void (doc.value = {});
		return load(name);
	},
	{ immediate: true }
);
</script>
