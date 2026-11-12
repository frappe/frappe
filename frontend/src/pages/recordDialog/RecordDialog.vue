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
		<!-- `pr-1` keeps the close button's gap; it follows the title slot with none. The subtitle hangs
		     below the row, so the header's height stays the row's and Dialog centres its close on the title. -->
		<template #title>
			<div class="relative flex items-center gap-1 pr-1">
				<h3
					:id="titleId"
					class="min-w-0 flex-1 break-words text-2xl-semibold leading-6 text-ink-gray-8"
				>
					{{ title }}
				</h3>
				<Button
					v-for="button in header.buttons"
					:key="button.label"
					variant="ghost"
					:icon="button.icon"
					:tooltip="button.label"
					:aria-label="button.label"
					:disabled="saving"
					@click="button.onClick"
				/>
				<Dropdown :options="menu" side="bottom" align="end">
					<Button variant="ghost" icon="lucide-ellipsis" :aria-label="__('More')" />
				</Dropdown>
				<p
					v-if="header.subtitle"
					class="absolute inset-x-0 top-full truncate pt-1 text-p-sm text-ink-gray-5"
				>
					{{ header.subtitle }}
				</p>
			</div>
		</template>
		<div ref="body" data-record-form :class="header.subtitle && 'pt-5'" :inert="saving">
			<component
				:is="Body"
				v-if="bodyShown"
				:page="controller!.page"
				:edit="edit"
				:header="setBodyHeader"
			/>
			<FormLayout
				v-else-if="form.length && !refused"
				v-model:doc="doc"
				v-model:tab="formTab"
				:layout="form"
				:doctype="doctype"
			/>
			<ErrorMessage v-if="error" class="mt-2" :message="error" />
		</div>
		<template v-if="showSave" #actions>
			<div class="flex justify-end">
				<Button
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
import { computed, inject, onUnmounted, ref, shallowRef, useId, useTemplateRef, watch } from "vue";
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
import { recordDialogBody } from "@/contributions/registry";
import { askRequired } from "@/pages/record/askRequired";
import { discardChanges } from "@/pages/record/discardChanges";
import { landOnField } from "@/pages/record/landOnField";
import { fetchMeta } from "@/pages/record/metaSource";
import { buttonClicks, provideRecordCommits } from "@/pages/record/recordCommits";
import { reportSaveFailure } from "@/pages/record/recordSave";
import { useUnloadGuard } from "@/unloadGuard";
import { loadRecord, saveRecord } from "@/pages/record/recordSource";
import { conflictError, stripTags } from "@/pages/record/saveResponse";
import { openArgumentStep } from "@/shell/palette";
import { urlFor } from "@/router/routeFor";
import type { Boot } from "@/boot";
import { announceRecordDialogWrite, type RecordDialogRequest } from "@/shell/recordDialog";
import { recordBodyComponent, type RecordBodyHeader } from "./recordBody";
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
const titleId = useId();
// reka names the dialog by its whole title header, so the icon buttons in it would join the name
// ("LEAD-1 More"): name it by the title text alone.
watch(body, (element) =>
	element?.closest('[role="dialog"]')?.setAttribute("aria-labelledby", titleId)
);
// A `pages.json` body draws in place of the form until the reader asks for the form.
const bodyLoader = recordDialogBody(doctype, boot.app);
const Body = bodyLoader ? recordBodyComponent(bodyLoader, bodyFailed) : null;
const editing = ref(false);
const bodyHeader = shallowRef<() => RecordBodyHeader>(() => ({}));

const quickEntry = useFormLayout({
	doctype,
	type: "Quick Entry",
	doc: openingValues,
	fallback: "meta",
	decorate: buttonClicks(() => controller.value),
	overrides: () => controller.value?.fields.resolve() ?? {},
	tabOverrides: () => controller.value?.form.tabs.resolve() ?? {},
});

const bodyShown = computed(() =>
	Boolean(Body && !editing.value && controller.value && !refused.value)
);
const header = computed<RecordBodyHeader>(() => (bodyShown.value ? readBodyHeader() : {}));
const title = computed(() => header.value.title || (doc.value.name ?? name));
const size = computed(() => quickEntry.dialogSize.value ?? "xl");
const canWrite = computed(() => Boolean(perms.value.write));
const showSave = computed(() => canWrite.value && header.value.save !== false);
const ready = computed(() => Boolean(controller.value?.ready.value) && !quickEntry.error.value);
const dirty = computed(() => JSON.stringify(doc.value) !== JSON.stringify(saved.value));
const layout = computed(() => quickEntry.layout.value);
const form = computed(() => {
	actionsVersion.value;
	const page = controller.value;
	return page ? joinForm(layout.value, page.form.resolve(), page.page) : layout.value;
});
const menu = computed(() => [
	...(header.value.menu?.length
		? [{ group: "body", hideLabel: true, options: header.value.menu }]
		: []),
	{
		group: "record",
		hideLabel: true,
		options: [
			{ label: __("Copy link"), icon: "lucide-link", onClick: copyLink },
			...(perms.value.delete
				? [{ label: __("Delete"), icon: "lucide-trash-2", theme: "red", onClick: remove }]
				: []),
		],
	},
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

function edit() {
	editing.value = true;
}

function setBodyHeader(read: () => RecordBodyHeader) {
	bodyHeader.value = read;
}

// A body's getter is its own code: one that throws keeps the record's header, as a `when` does.
function readBodyHeader(): RecordBodyHeader {
	try {
		return bodyHeader.value();
	} catch (exception) {
		console.error(exception);
		return {};
	}
}

function bodyFailed(exception: unknown) {
	edit();
	error.value = errorMessage(exception);
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
		saveFailed: reportSaveFailure,
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
		if (await controller.value.page.save()) isOpen.value = false;
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
	if (!event.repeat && showSave.value) void save();
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
