<!-- The Preview tab: the record page's own FormLayout on a copy of one record. It never writes:
     typing changes only the copy, NO_COMMIT drops the field events and uploads are refused. -->
<template>
	<div class="mx-auto w-full max-w-3xl py-4" data-editor-preview>
		<div class="mb-1 flex items-center gap-2">
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
						<span class="truncate text-ink-gray-8">{{
							record ?? __("an empty form")
						}}</span>
						<span class="lucide-chevron-down size-4 shrink-0" aria-hidden="true" />
					</button>
				</template>
			</Combobox>
			<span v-if="loading" class="text-p-sm text-ink-gray-5">{{ __("Loading…") }}</span>
			<span class="ml-auto shrink-0 text-p-sm text-ink-gray-5">{{
				__("Changes here are not saved.")
			}}</span>
		</div>
		<FormLayout
			:key="record ?? EMPTY"
			v-model:doc="doc"
			v-model:tab="tab"
			:layout="details.layout.value"
			:doctype="doctype"
			:class="FORM_CLASSES"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, provide, ref, watch } from "vue";
import { Combobox } from "frappe-ui";
import { getDocument } from "@framework/ui/api";
import { UploadTransportKey } from "@framework/ui/FileUpload";
import { FormLayout } from "@framework/ui/FormLayout";
import { CommitKey, NO_COMMIT } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import { FORM_CLASSES } from "@/pages/record/formClasses";
import { useFormLayout } from "@/recordPage/formLayoutSource/useFormLayout";

const props = defineProps<{ doctype: string; record: string | null; latest: string[] }>();
const emit = defineEmits<{ pick: [name: string | null] }>();

const EMPTY = "__empty__";
provide(CommitKey, NO_COMMIT);
provide(UploadTransportKey, async () => {
	throw new Error(__("Preview does not upload files."));
});

const doc = ref<Record<string, any>>({});
const tab = ref("");
const loading = ref(false);
const details = useFormLayout({
	doctype: () => props.doctype,
	type: "Details",
	doc,
	fallback: "meta",
});

const options = computed(() => [
	{ label: __("Empty form"), value: EMPTY },
	...props.latest.map((name) => ({ label: name, value: name })),
]);

watch(
	() => props.record,
	async (name) => {
		if (!name) return void (doc.value = {});
		loading.value = true;
		try {
			const { data } = await getDocument(props.doctype, name);
			if (props.record === name) doc.value = structuredClone(data);
		} catch {
			if (props.record === name) emit("pick", null);
		} finally {
			loading.value = false;
		}
	},
	{ immediate: true }
);
</script>
