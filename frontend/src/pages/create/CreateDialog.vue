<!-- One Create request: the doctype's Quick Entry form, inserted on save, or the full-page new
     record when the server says the doctype gets no dialog. -->
<template>
	<Dialog
		v-if="shown"
		v-model:open="isOpen"
		:title="__('New {0}', [__(doctype)])"
		size="xl"
		@after-leave="request.dismiss()"
	>
		<div @keydown.enter.ctrl.prevent="save" @keydown.enter.meta.prevent="save">
			<FormLayout v-if="layout.length" v-model:doc="doc" :layout="layout" />
			<ErrorMessage v-if="error" class="mt-2" :message="error" />
		</div>
		<template #actions>
			<div class="flex items-center justify-between gap-2">
				<Button
					variant="ghost"
					:label="__('Edit full form')"
					:disabled="saving"
					@click="editFullForm"
				/>
				<Button variant="solid" :label="__('Save')" :loading="saving" @click="save" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, provide, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Button, Dialog, ErrorMessage } from "frappe-ui";
import { createDocument, runMethod } from "@framework/ui/api";
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
import { fieldDefaults, fillEmpty, insertBody, typedValues, withNameField } from "./createForm";

const GET_NEW_DOC = "frappe.desk.form.load.get_new_doc";

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
	conditionDoc.value = { ...current, ...values };
});

let unmounted = false;
onBeforeUnmount(() => (unmounted = true));

runMethod<Record<string, any>>(GET_NEW_DOC, { doctype }, { http: "GET" }).then(
	({ data }) => (newDoc.value = data),
	(exception) => (error.value = errorMessage(exception))
);

quickEntry.settled().then(() => {
	if (unmounted) return;
	if (!quickEntry.error.value && !quickEntry.dialog.value) {
		props.request.dismiss();
		return handOver(values);
	}
	if (quickEntry.error.value) error.value = errorMessage(quickEntry.error.value);
	shown.value = true;
});

watch(isOpen, (open) => {
	if (!open) props.request.settle(null);
});

async function save() {
	if (saving.value) return;
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
