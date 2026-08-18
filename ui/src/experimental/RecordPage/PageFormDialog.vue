<template>
	<!-- `page.dialog.form()`'s host: the declarative tier, so a script that cannot
	     ship a component still gets a real form. The doc is local and dies with
	     the dialog — nothing here touches the record behind it. -->
	<Dialog
		v-model:open="isOpen"
		:title="options.title || 'Dialog'"
		:size="size"
		:dismissible="dismissible"
		:show-close-button="dismissible"
		@after-leave="entry.dismiss()"
	>
		<FormLayout v-if="layout.length" v-model:doc="doc" :layout="layout" />
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
				<!-- v1's rule: the Cancel button appears only when it is labelled.
				     Esc, the backdrop and the X close the dialog either way. -->
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
import { computed, reactive, ref, watch } from "vue";
import { Button, Dialog, ErrorMessage } from "frappe-ui";
import type { DialogSize } from "frappe-ui";
import { FormLayout } from "../../components/FormLayout";
import type { FormLayoutSchema } from "../../components/FormLayout/types";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { useDocPermissions } from "../../composables/useDocPermissions";
import { useFormLayout } from "../FormLayoutSource";
import { errorMessage } from "../errorMessage";
import {
	applyRequired,
	formData,
	initialDoc,
	layoutFromFields,
	layoutFromTabs,
	layoutMode,
	missingRequired,
	pickMetaFields,
	warnAmbiguousLayout,
} from "./formDialogLayout";
import type { PageDialogEntry } from "./dialog";
import type { PageDialogAction } from "./types";

const props = defineProps<{ entry: PageDialogEntry }>();

const options = props.entry.form!;
const mode = layoutMode(options);
warnAmbiguousLayout(options);

const isOpen = ref(true);
const error = ref("");
const submitting = ref(false);
const actionLoading = reactive((options.actions ?? []).map(() => false));

const doc = ref<Record<string, any>>({ ...(options.defaults ?? {}) });
// Conditions on a `Quick Entry` row read this, not the live draft: a layout that
// switched mid-keystroke would remount the form and steal the reader's focus.
const conditionDoc = ref<Record<string, any>>({ ...(options.defaults ?? {}) });

// Two sources, because the two `doctype` shapes ask different questions: the
// whole form is the doctype's `Quick Entry` layout, while a picked handful is
// taken from the meta — the layout is a curated subset that need not contain
// what the author named.
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

function baseLayout(): FormLayoutSchema {
	if (mode === "fields") return layoutFromFields(options.fields!);
	if (mode === "tabs") return layoutFromTabs(options.tabs!);
	if (mode !== "doctype") return [];
	if (!options.fieldnames) return quickEntry!.layout.value;
	return pickMetaFields(
		doctypeMeta!.meta.value?.fields,
		options.fieldnames,
		permissions!.fieldAccess,
	);
}

// `doctype` mode resolves its fields a fetch later than the dialog opens, so the
// doc gains their keys when they arrive — edits already made are kept.
watch(
	layout,
	(current) => {
		doc.value = { ...initialDoc(current, options.defaults), ...doc.value };
	},
	{ immediate: true },
);

const dismissible = options.dismissible !== false;
const size = (options.size as DialogSize) ?? "xl";
const busy = computed(() => submitting.value || actionLoading.some(Boolean));

// True once we know what to tell the author, so neither `onCancel` nor the
// promise can be answered twice — the ways out overlap (Esc mid-transition, a
// page that unmounts while the dialog animates away).
let answered = false;

function dismissed() {
	if (answered) return;
	answered = true;
	options.onCancel?.();
}

// Every way out that is not an explicit `close(value)` — Esc, the backdrop, the
// X, Cancel — lands in the watcher; navigating off the record never gets there,
// since the host unmounts this component, so it is routed through `onDismissed`.
props.entry.onDismissed = dismissed;

watch(isOpen, (open) => {
	if (open) return;
	dismissed();
	props.entry.settle(null);
});

// The promise settles the moment the answer is known, not when the leave
// transition ends — a page unmounting in that window must not turn a submitted
// dialog into a cancelled one.
function close(value: any = null) {
	answered = true;
	props.entry.settle(value);
	isOpen.value = false;
}

function cancel() {
	isOpen.value = false;
}

function validate(): boolean {
	const missing = missingRequired(layout.value, doc.value);
	error.value = missing.length ? `Please fill in ${missing.join(", ")}` : "";
	return missing.length === 0;
}

async function submit() {
	if (busy.value || !validate()) return;
	submitting.value = true;
	error.value = "";
	try {
		const data = formData(layout.value, doc.value);
		await options.onSubmit?.(data);
		close(data);
	} catch (exception) {
		// The author's `onSubmit` threw: hold the dialog open with the error
		// inline, so a failed server call can be corrected and retried.
		report("onSubmit", exception);
	} finally {
		submitting.value = false;
	}
}

// The reader gets the message; the console gets the script's name, matching 08's
// error story — a dialog that keeps failing has to be traceable to a source.
function report(hook: string, exception: unknown) {
	error.value = errorMessage(exception);
	console.error(`[record-page] ${props.entry.source} page.dialog.form ${hook} threw`, exception);
}

// A custom action never closes on its own — `close(result)` is how it resolves
// the promise, which is what lets one dialog answer with more than a submit.
async function runAction(action: PageDialogAction, index: number) {
	if (busy.value) return;
	actionLoading[index] = true;
	error.value = "";
	try {
		if (!action.onClick) {
			if (validate()) close(formData(layout.value, doc.value));
			return;
		}
		await action.onClick({
			data: formData(layout.value, doc.value),
			close,
			validate,
		});
	} catch (exception) {
		report(`action "${action.label}"`, exception);
	} finally {
		actionLoading[index] = false;
	}
}
</script>
