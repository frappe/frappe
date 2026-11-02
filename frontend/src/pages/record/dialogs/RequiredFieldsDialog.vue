<!-- The body of the dialog a save opens for the mandatory fields the layout does not show. -->
<template>
	<div ref="body">
		<p class="text-p-sm text-ink-gray-7">
			{{ __("These fields are required but are not on this form.") }}
		</p>
		<p v-if="canCustomize" class="mt-1 text-p-sm text-ink-gray-6" data-customize-note>
			{{ __("Add them to the Details layout so people can see them on the form.") }}
		</p>
		<FormLayout
			class="mt-4"
			v-model:doc="values"
			v-model:tab="tab"
			:layout="layout"
			:doctype="doctype"
		/>
	</div>
	<div class="mt-5 flex flex-row-reverse gap-2">
		<Button
			variant="solid"
			:label="submitting ? __('Save and submit') : __('Continue')"
			@click="submit"
		/>
		<Button variant="outline" :label="__('Cancel')" @click="close()" />
	</div>
</template>

<script setup lang="ts">
import { computed, provide, ref, useTemplateRef } from "vue";
import { Button } from "frappe-ui";
import { FormLayout } from "@framework/ui/FormLayout";
import { CommitKey, NO_COMMIT } from "@framework/ui/FormLayout/types";
import type { FormLayoutSchema } from "@framework/ui/FormLayout/types";
import { FieldErrorsKey, RecordLinkKey } from "@framework/ui/fields/types";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { useUserRoles } from "@framework/ui/useUserRoles";
import { __ } from "@/i18n";
import { FieldErrors, missingRequired } from "@/recordPage";
import { formData } from "@/recordPage/formDialogLayout";
import { landOnFirstMarked } from "../landOnField";

const props = defineProps<{
	layout: FormLayoutSchema;
	/** The record, so `depends_on` and `fetch_from` read what the reader has filled. */
	doc: Record<string, any>;
	doctype: string;
	/** A Submit asked it: the primary button then saves and submits. */
	submitting?: boolean;
	close: (value?: any) => void;
}>();

// Its own marks and no commits, so the record's handlers and errors stay out of the dialog.
const errors = new FieldErrors();
provide(FieldErrorsKey, errors.drawn);
provide(CommitKey, errors.clearingOnEdit(NO_COMMIT));
provide(RecordLinkKey, null);

const values = ref<Record<string, any>>({ ...props.doc });
const tab = ref("");
const body = useTemplateRef<HTMLElement>("body");

// The Customize Form check reads that doctype's meta, which loads only when this dialog opens.
const { roles } = useUserRoles();
const customizer = useDocPermissions("Customize Form");
const canCustomize = computed(
	() => roles.value?.includes("System Manager") && customizer.holds("write")
);

function submit() {
	errors.clearAll();
	const missing = missingRequired(props.layout, values.value);
	for (const { address, message } of missing) errors.mark(address, message);
	if (missing.length) return landOnFirstMarked(errors, landing, values.value);
	props.close(formData(props.layout, values.value));
}

const landing = {
	root: () => body.value,
	layout: () => props.layout,
	showTab: (identity: string) => void (tab.value = identity),
};
</script>
