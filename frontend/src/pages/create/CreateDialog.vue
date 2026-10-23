<!-- One Create request: the doctype's Quick Entry form, inserted on save, or the full-page new
     record when the server says the doctype gets no dialog. -->
<template>
	<Dialog
		v-if="shown"
		v-model:open="isOpen"
		:title="__('New {0}', [__(doctype)])"
		:dismissible="!saving"
		:show-close-button="!saving"
		size="xl"
		@after-leave="request.dismiss()"
	>
		<div ref="body">
			<FormLayout
				v-if="layout.length"
				v-model:doc="doc"
				:layout="layout"
				autofocus
				@update:doc="typed = true"
			/>
			<ErrorMessage v-if="error" class="mt-2" :message="error" />
		</div>
		<template #actions>
			<div class="flex items-center justify-between gap-2">
				<Button
					variant="subtle"
					:label="__('Edit full form')"
					:disabled="saving"
					@click="editFullForm"
				/>
				<Button
					variant="solid"
					:label="__('Save')"
					:loading="saving"
					:disabled="layoutFailed"
					@click="save"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, provide, ref, useTemplateRef, watch } from "vue";
import { useRouter } from "vue-router";
import { useEventListener } from "@vueuse/core";
import { Button, Dialog, ErrorMessage } from "frappe-ui";
import { createDocument } from "@framework/ui/api";
import { FormLayout } from "@framework/ui/components/FormLayout";
import { CommitKey, NO_COMMIT } from "@framework/ui/components/FormLayout/types";
import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import { useDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { __ } from "@/i18n";
import { useFormLayout } from "@/recordPage";
import { errorMessage } from "@/recordPage/errorMessage";
import { formData, initialDoc, missingRequired } from "@/recordPage/formDialogLayout";
import { routeForNew } from "@/router/routeFor";
import type { CreateRequest } from "@/shell/create";
import {
	fetchNewDocument,
	fieldDefaults,
	fillEmpty,
	insertBody,
	typedValues,
	withNameField,
} from "@/newRecordValues";

// The dialog's fields commit to nothing, or they would fire a record page's handlers.
provide(CommitKey, NO_COMMIT);

const props = defineProps<{ request: CreateRequest }>();
const { doctype, values } = props.request;

const router = useRouter();
const { meta } = useDoctypeMeta(doctype);
// A row's condition reads this, not the live draft: a layout switch mid-keystroke steals focus.
const conditionDoc = ref<Record<string, any>>({ ...values });
const quickEntry = useFormLayout({
	doctype,
	type: "Quick Entry",
	doc: conditionDoc,
	fallback: "meta",
});

const shown = ref(false);
const isOpen = ref(true);
const saving = ref(false);
const error = ref("");
const newDoc = ref<Record<string, any> | null>(null);
const doc = ref<Record<string, any>>({ ...values });
const typed = ref(false);

const layout = computed<FormLayoutSchema>(() =>
	withNameField(quickEntry.layout.value, meta.value)
);
const defaults = computed(() => (newDoc.value ? fieldDefaults(newDoc.value, meta.value) : {}));

watch(
	layout,
	(current) => {
		doc.value = { ...initialDoc(current, values), ...doc.value };
	},
	{ immediate: true }
);

watch(defaults, (current) => {
	doc.value = fillEmpty(doc.value, current);
	// After the person types, the row stays: a layout switch mid-edit moves the fields.
	if (!typed.value) conditionDoc.value = { ...current, ...values };
});

fetchNewDocument(doctype).then(
	(data) => (newDoc.value = data),
	(exception) => (error.value = errorMessage(exception))
);

const layoutFailed = computed(() => Boolean(quickEntry.error.value));

quickEntry.settled().then(() => {
	if (props.request.settled()) return;
	if (!layoutFailed.value && !quickEntry.dialog.value) {
		props.request.dismiss();
		return handOver(values);
	}
	if (layoutFailed.value) error.value = errorMessage(quickEntry.error.value);
	shown.value = true;
});

watch(isOpen, (open) => {
	if (!open) props.request.settle(null);
});

// The dialog's content is teleported, so the shortcut is caught on the document.
const body = useTemplateRef<HTMLElement>("body");
useEventListener(document, "keydown", (event: KeyboardEvent) => {
	if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey)) return;
	if (!body.value?.closest('[role="dialog"]')?.contains(event.target as Node)) return;
	event.preventDefault();
	void save();
});

async function save() {
	if (saving.value || layoutFailed.value) return;
	const missing = missingRequired(layout.value, doc.value);
	if (missing.length) {
		error.value = __("Please fill in {0}", [missing.join(", ")]);
		return;
	}
	saving.value = true;
	error.value = "";
	try {
		const { data } = await createDocument(
			doctype,
			insertBody(values, formData(layout.value, doc.value))
		);
		props.request.settle(data);
		isOpen.value = false;
	} catch (exception) {
		error.value = errorMessage(exception);
	} finally {
		saving.value = false;
	}
}

function editFullForm() {
	const typed = typedValues(values, formData(layout.value, doc.value), defaults.value);
	isOpen.value = false;
	handOver(typed);
}

function handOver(carried: Record<string, any>) {
	props.request.settle(null);
	void router.push(routeForNew(doctype, carried));
}
</script>
