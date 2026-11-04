<!-- One record opened as a dialog: the doctype's Quick Entry form over the page it opened on.
     A record script runs as on the page; the header, tabs, feed, files and composer are not drawn. -->
<template>
	<Dialog
		v-if="shown"
		:open="isOpen"
		:title="title"
		:dismissible="!saving"
		:show-close-button="!saving"
		:size="size"
		@update:open="close"
		@after-leave="request.dismiss()"
	>
		<div ref="body" data-record-form :inert="saving">
			<FormLayout
				v-if="form.length && !refused"
				v-model:doc="doc"
				v-model:tab="formTab"
				:layout="form"
				:doctype="doctype"
			/>
			<ErrorMessage v-if="error" class="mt-2" :message="error" />
		</div>
		<template #actions>
			<div class="flex items-center justify-between gap-2">
				<Dropdown :options="menu" side="top" align="start">
					<Button variant="ghost" icon="lucide-ellipsis" :aria-label="__('More')" />
				</Dropdown>
				<Button
					v-if="canWrite"
					variant="solid"
					:label="__('Save')"
					:loading="saving"
					:disabled="!ready"
					@click="save"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, inject, onUnmounted, ref, shallowRef, useTemplateRef, watch } from "vue";
import { useRouter } from "vue-router";
import { useEventListener } from "@vueuse/core";
import { Button, Dialog, Dropdown, ErrorMessage, toast } from "frappe-ui";
import { deleteDocument, isApiError } from "@framework/ui/api";
import { FormLayout } from "@framework/ui/FormLayout";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { __ } from "@/i18n";
import {
	createRecordPage,
	errorMessage,
	formItems,
	joinForm,
	loadRecordScripts,
	useFormLayout,
	type RecordPageController,
} from "@/recordPage";
import { askRequired } from "@/pages/record/askRequired";
import { discardChanges } from "@/pages/record/discardChanges";
import { landOnField } from "@/pages/record/landOnField";
import { fetchMeta } from "@/pages/record/metaSource";
import { buttonClicks, provideRecordCommits } from "@/pages/record/recordCommits";
import { runSave, useUnloadGuard } from "@/pages/record/recordSave";
import { loadRecord, saveRecord } from "@/pages/record/recordSource";
import { conflictError, stripTags } from "@/pages/record/saveResponse";
import { openArgumentStep } from "@/shell/palette";
import { urlFor } from "@/router/routeFor";
import type { Boot } from "@/boot";
import { announceRecordDialogWrite, type RecordDialogRequest } from "@/shell/recordDialog";
import { resolveSaveConflict } from "./saveConflict";

const props = defineProps<{ request: RecordDialogRequest }>();
const { doctype, name } = props.request;

const boot = inject<Boot>("boot")!;
const router = useRouter();
const { metas } = useDoctypeMeta(doctype);
provideRecordCommits(() => controller.value);

const doc = ref<Record<string, any>>({});
const saved = ref<Record<string, any>>({});
const meta = ref<any>(null);
const perms = ref<Record<string, any>>({});
// The values the layout row is picked against, set once, so typing never switches the row.
const openingValues = ref<Record<string, any>>({});
const controller = shallowRef<RecordPageController | null>(null);
let unmounted = false;
const shown = ref(false);
const isOpen = ref(true);
const saving = ref(false);
const error = ref("");
const refused = ref(false);
const formTab = ref("");
const activeFormTab = ref("");
const actionsVersion = ref(0);
const body = useTemplateRef<HTMLElement>("body");

const quickEntry = useFormLayout({
	doctype,
	type: "Quick Entry",
	doc: openingValues,
	fallback: "meta",
	decorate: buttonClicks(() => controller.value),
	overrides: () => controller.value?.fields.resolve() ?? {},
	tabOverrides: () => controller.value?.form.tabs.resolve() ?? {},
});

const title = computed(() => doc.value.name ?? name);
const size = computed(() => quickEntry.dialogSize.value ?? "xl");
const canWrite = computed(() => Boolean(perms.value.write));
const ready = computed(() => Boolean(controller.value?.ready.value) && !quickEntry.error.value);
const dirty = computed(() => JSON.stringify(doc.value) !== JSON.stringify(saved.value));
const layout = computed(() => quickEntry.layout.value);
const form = computed(() => {
	actionsVersion.value;
	const page = controller.value;
	return page ? joinForm(layout.value, page.form.resolve(), page.page) : layout.value;
});
const menu = computed(() => [
	{ label: __("Copy link"), icon: "lucide-link", onClick: copyLink },
	...(perms.value.delete
		? [{ label: __("Delete"), icon: "lucide-trash-2", theme: "red", onClick: remove }]
		: []),
]);

void open();

/** Meta, the record and its layout at once; a refusal shows as text, as the page's state would. */
async function open() {
	void loadRecordScripts(doctype);
	try {
		meta.value = await fetchMeta(doctype);
		const loaded = await loadRecord(doctype, name);
		perms.value = loaded.docinfo.permissions ?? {};
		if (!perms.value.read) throw Object.assign(new Error("denied"), { status: 403 });
		saved.value = { ...loaded.document };
		doc.value = JSON.parse(JSON.stringify(loaded.document));
		openingValues.value = JSON.parse(JSON.stringify(loaded.document));
	} catch (exception) {
		refused.value = true;
		error.value =
			isApiError(exception) || (exception as any)?.status === 403
				? __("You do not have permission to open this record")
				: errorMessage(exception);
		shown.value = true;
		return;
	}
	if (unmounted) return;
	const created = controller.value ?? buildController();
	await Promise.all([quickEntry.settled(), created.refresh()]);
	if (quickEntry.error.value) error.value = errorMessage(quickEntry.error.value);
	shown.value = true;
	actionsVersion.value++;
}

function buildController() {
	const created = createRecordPage({
		app: boot.app!,
		doctype,
		docname: name,
		doc,
		saved,
		meta,
		perms: () => perms.value,
		isDirty: () => dirty.value,
		activeTab: () => "details",
		activateTab: () => {},
		formLayout: () => layout.value,
		offLayout: () => quickEntry.offLayout.value,
		askRequired: (asked) => askRequired(created.page.dialog, asked, doc.value, doctype),
		activeFormTab: () => activeFormTab.value,
		activateFormTab: (identity) => void (formTab.value = identity),
		focusField: (fieldname, cursor) => void landOnField(landing, fieldname, cursor),
		save: write,
		reload: open,
		router,
		childFields: (child) => metas.value[child]?.fields,
		sourcesReady: () => loadRecordScripts(doctype),
		actFailed: (exception) => toast.error(errorMessage(exception)),
		openArgument: openArgumentStep,
		activityRows: () => [],
		scrollToActivity: async () => false,
		reloadActivity: async () => {},
		fileRows: () => [],
		reloadFiles: async () => {},
	});
	created.form.provideBuiltins(() => formItems(layout.value));
	controller.value = created;
	return created;
}

async function write() {
	try {
		const document = await saveRecord(doctype, doc.value);
		saved.value = { ...document };
		doc.value = JSON.parse(JSON.stringify(document));
		announceRecordDialogWrite(doctype);
		await controller.value?.refresh().catch(() => {});
		actionsVersion.value++;
	} catch (exception) {
		if (isApiError(exception) && exception.isTimestampMismatch) {
			await resolveSaveConflict(exception, controller.value!.page.dialog.confirm, {
				doctype,
				name,
				doc: doc.value,
				saved: saved.value,
				fields: meta.value?.fields,
				reload: open,
			});
			throw conflictError();
		}
		if (isApiError(exception))
			controller.value?.fieldErrors.markRefused(exception.fieldErrors, doc.value);
		throw isApiError(exception) ? new Error(stripTags(exception.message)) : exception;
	}
}

async function save() {
	if (saving.value || !controller.value) return;
	error.value = "";
	saving.value = true;
	try {
		if (await runSave(controller.value.page)) isOpen.value = false;
	} finally {
		saving.value = false;
	}
}

// Closing with edits asks first, while the dialog is still up: leaving it would close the question.
async function close(next: boolean) {
	if (next || !dirty.value || !controller.value || saving.value) {
		isOpen.value = next;
		return;
	}
	if (await discardChanges(controller.value.page.dialog.confirm)) isOpen.value = false;
}

async function remove() {
	const page = controller.value?.page;
	if (
		!page ||
		!(await page.dialog.danger({
			title: __("Delete this record?"),
			message: __("{0} will be deleted.", [name]),
		}))
	)
		return;
	try {
		await deleteDocument(doctype, name);
		saved.value = { ...doc.value };
		announceRecordDialogWrite(doctype);
		isOpen.value = false;
	} catch (exception) {
		toast.error(errorMessage(exception));
	}
}

async function copyLink() {
	await navigator.clipboard.writeText(new URL(urlFor(doctype, name), location.origin).href);
	toast.success(__("Link copied"));
}

// On the document: the form is inert while saving, so focus is on the page after a failed save.
useEventListener(document, "keydown", (event: KeyboardEvent) => {
	if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "s") return;
	const dialog = body.value?.closest('[role="dialog"]');
	const inside =
		event.target instanceof Element ? event.target.closest('[role="dialog"]') : null;
	if (inside && inside !== dialog) return;
	event.preventDefault();
	if (!event.repeat && canWrite.value) void save();
});

const landing = {
	root: () => body.value,
	layout: () => form.value,
	showTab: (identity: string) => void (formTab.value = identity),
};

useUnloadGuard(() => dirty.value);

onUnmounted(() => {
	unmounted = true;
	controller.value?.leave();
});
</script>
