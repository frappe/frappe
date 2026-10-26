<!-- `page.dialog.form()`'s host: the declarative tier. The doc is local and dies with the
     dialog; nothing here touches the record behind it. -->
<template>
	<Dialog
		v-model:open="isOpen"
		:title="options.title || 'Dialog'"
		:size="size"
		:dismissible="dismissible"
		:show-close-button="dismissible"
		@after-leave="entry.dismiss()"
	>
		<div ref="body">
			<FormLayout
				v-if="layout.length"
				v-model:doc="doc"
				v-model:tab="formTab"
				:layout="layout"
			/>
			<FormSkeleton v-else-if="layoutLoading" :columns="1" :fields="4" />
		</div>
		<ErrorMessage v-if="error" class="mt-2" :message="error" />
		<template #actions>
			<div v-if="options.actions?.length" class="flex justify-end gap-2">
				<Button
					v-for="(action, index) in options.actions"
					:key="action.label"
					:label="action.label"
					:variant="(action.variant as any) ?? 'subtle'"
					:theme="action.theme as any"
					:icon-left="action.icon"
					:loading="actionLoading[index]"
					:disabled="busy && !actionLoading[index]"
					@click="runAction(action, index)"
				/>
			</div>
			<div v-else class="flex flex-row-reverse gap-2">
				<Button
					variant="solid"
					:label="options.submitLabel || 'Submit'"
					:loading="submitting"
					@click="submit"
				/>
				<!-- Desk v1's rule: the Cancel button appears only when it is labelled. -->
				<Button
					v-if="options.cancelLabel"
					variant="outline"
					:label="options.cancelLabel"
					:disabled="submitting"
					@click="cancel"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, provide, reactive, ref, useTemplateRef, watch } from "vue";
import { Button, Dialog, ErrorMessage } from "frappe-ui";
import type { DialogSize } from "frappe-ui";
import { FormLayout } from "@framework/ui/FormLayout";
import { CommitKey, NO_COMMIT } from "@framework/ui/FormLayout/types";
import { FieldErrorsKey, RecordLinkKey } from "@framework/ui/fields/types";
import type { FormLayoutSchema } from "@framework/ui/FormLayout/types";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { FieldErrors, missingRequired, useFormLayout } from "@/recordPage";
import type { PageDialogEntry } from "@/recordPage/dialog";
import { errorMessage } from "@/recordPage/errorMessage";
import {
	applyRequired,
	formData,
	initialDoc,
	layoutFromFields,
	layoutFromTabs,
	layoutMode,
	pickMetaFields,
	warnAmbiguousLayout,
} from "@/recordPage/formDialogLayout";
import type { PageDialogAction } from "@/recordPage/types";
import FormSkeleton from "../skeletons/FormSkeleton.vue";
import { landOnFirstMarked } from "../landOnField";

// Its own marks, so the record's do not show in the dialog's fields.
const errors = new FieldErrors();
provide(FieldErrorsKey, errors.drawn);
// The dialog's fields commit to nothing, or they would fire the record's handlers under the same names.
provide(CommitKey, errors.clearingOnEdit(NO_COMMIT));
// A dialog has no guard for its unsaved values, so its Link fields open nothing.
provide(RecordLinkKey, null);

const props = defineProps<{ entry: PageDialogEntry }>();

const options = props.entry.form!;
const mode = layoutMode(options);
warnAmbiguousLayout(options);

const isOpen = ref(true);
const error = ref("");
const submitting = ref(false);
const formTab = ref("");
const body = useTemplateRef<HTMLElement>("body");
const actionLoading = reactive((options.actions ?? []).map(() => false));

const doc = ref<Record<string, any>>({ ...(options.defaults ?? {}) });
// A `Quick Entry` row's condition reads this, not the live draft: a layout switch mid-keystroke steals focus.
const conditionDoc = ref<Record<string, any>>({ ...(options.defaults ?? {}) });

// The whole form is the doctype's `Quick Entry` layout; a picked handful comes from the meta.
const quickEntry =
	mode === "doctype" && !options.fieldnames
		? useFormLayout({
				doctype: options.doctype!,
				type: "Quick Entry",
				doc: conditionDoc,
				fallback: "meta",
		  })
		: null;

const picked = options.fieldnames ? options.doctype! : null;
const doctypeMeta = picked ? useDoctypeMeta(picked) : null;
const permissions = picked ? useDocPermissions(picked) : null;

const layout = computed<FormLayoutSchema>(() => applyRequired(baseLayout(), options.required));
const layoutLoading = computed(() =>
	Boolean(quickEntry?.loading.value || doctypeMeta?.loading.value)
);

function baseLayout(): FormLayoutSchema {
	if (mode === "fields") return layoutFromFields(options.fields!);
	if (mode === "tabs") return layoutFromTabs(options.tabs!);
	if (mode !== "doctype") return [];
	if (!options.fieldnames) return quickEntry!.layout.value;
	return pickMetaFields(
		doctypeMeta!.meta.value?.fields,
		options.fieldnames,
		permissions!.fieldAccess
	);
}

// `doctype` mode resolves its fields a fetch later than the dialog opens; edits already made are kept.
watch(
	layout,
	(current) => {
		doc.value = { ...initialDoc(current, options.defaults), ...doc.value };
	},
	{ immediate: true }
);

const dismissible = options.dismissible !== false;
const size = (options.size as DialogSize) ?? "xl";
const busy = computed(() => submitting.value || actionLoading.some(Boolean));

// The ways out overlap (Esc mid-transition, a page unmounting), so the author hears `onCancel` once.
let answered = false;

function dismissed() {
	if (answered) return;
	answered = true;
	props.entry
		.hold(() => options.onCancel?.())
		.catch((exception) => report("onCancel", exception));
}

// Navigating off the record unmounts this component before the watcher below can run.
props.entry.onDismissed = dismissed;

watch(isOpen, (open) => {
	if (open) return;
	dismissed();
	props.entry.settle(null);
});

// Settled now, not on `after-leave`: a page unmounting mid-transition must not turn a submit into a cancel.
function close(value: any = null) {
	answered = true;
	props.entry.settle(value);
	isOpen.value = false;
}

function cancel() {
	isOpen.value = false;
}

function validate(): boolean {
	errors.clearAll();
	error.value = "";
	const missing = missingRequired(layout.value, doc.value);
	for (const { address, message } of missing) errors.mark(address, message);
	if (missing.length) landOnFirstMarked(errors, landing, doc.value);
	return missing.length === 0;
}

const landing = {
	root: () => body.value,
	layout: () => layout.value,
	showTab: (identity: string) => void (formTab.value = identity),
};

async function submit() {
	if (busy.value || !validate()) return;
	submitting.value = true;
	error.value = "";
	try {
		const data = formData(layout.value, doc.value);
		await props.entry.hold(() => options.onSubmit?.(data));
		close(data);
	} catch (exception) {
		// The dialog stays open with the error inline, so a failed server call can be retried.
		report("onSubmit", exception);
	} finally {
		submitting.value = false;
	}
}

// The reader gets the message; the console gets the script's name.
function report(hook: string, exception: unknown) {
	error.value = errorMessage(exception);
	console.error(`[record-page] ${props.entry.source} page.dialog.form ${hook} threw`, exception);
}

// A custom action never closes on its own; `close(result)` is how it resolves the promise.
async function runAction(action: PageDialogAction, index: number) {
	if (busy.value) return;
	actionLoading[index] = true;
	error.value = "";
	try {
		const onClick = action.onClick;
		if (!onClick) {
			if (validate()) close(formData(layout.value, doc.value));
			return;
		}
		await props.entry.hold(() =>
			onClick({
				data: formData(layout.value, doc.value),
				close,
				validate,
			})
		);
	} catch (exception) {
		report(`action "${action.label}"`, exception);
	} finally {
		actionLoading[index] = false;
	}
}
</script>
