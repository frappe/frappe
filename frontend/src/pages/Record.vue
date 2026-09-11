<!--
  The generated record page every app gets at /apps/<prefix>/<slug>/<name>: a host for the
  record-page engine with a header row, the Details form, the panel and its own scroll.
-->
<template>
	<PageFrame :scroll="false">
		<template v-if="doctype" #header>
			<RecordHeader
				v-if="controller"
				:projection="header"
				:dirty="dirty"
				:saving="saving"
				@run="runAction"
			/>
			<div v-else class="flex items-center gap-3">
				<h1 class="text-lg font-semibold">{{ route.params.name }}</h1>
				<span class="text-sm text-ink-gray-5">{{ doctype }}</span>
			</div>
		</template>

		<p v-if="!doctype" class="py-5 text-sm text-ink-gray-6" :class="pageGutter">
			No doctype is served at <code>{{ route.params.doctype }}</code> under this prefix.
		</p>

		<div v-else class="flex min-h-0 flex-1">
			<ScrollArea class="min-h-0 flex-1" :viewportClass="[pageGutter, 'py-5']">
				<p v-if="actionError" class="mb-3 text-sm text-ink-red-4">{{ actionError }}</p>
				<p v-if="error" class="text-sm text-ink-red-4">{{ error }}</p>

				<div v-else-if="controller" ref="formRoot" class="max-w-4xl" data-record-form>
					<FormLayout
						v-if="form.length"
						v-model:doc="doc"
						:layout="form"
						:tab="formTab"
						@update:tab="chooseFormTab"
						@update:activeTab="activeFormTab = $event"
					/>
				</div>
			</ScrollArea>

			<RecordPanel
				v-if="controller && !error"
				v-model:doc="doc"
				:user="boot.user.name"
				:doctype="doctype"
				:docname="docname"
				:controller="controller"
				:meta="meta"
				:docinfo="docinfo"
				:sections="sections"
				:disclosure="disclosure"
				:run="runAction"
				@expand="expand"
			/>
		</div>

		<PageDialogs v-if="controller" :controller="controller" />
	</PageFrame>
</template>

<script setup lang="ts">
import {
	computed,
	inject,
	nextTick,
	onMounted,
	onUnmounted,
	provide,
	ref,
	shallowRef,
	watch,
} from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import { ScrollArea, toast } from "frappe-ui";
import { FormLayout } from "@framework/ui/components/FormLayout";
import { CommitKey, LinkTitlesKey } from "@framework/ui/components/Fields/types";
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import { identifyTabs } from "@framework/ui/components/FormLayout/tabIdentity";
import {
	createRecordPage,
	errorMessage,
	loadClientScripts,
	projectHeader,
	useFormLayout,
	type HeaderItem,
	type QuickAction,
	type RecordPageController,
} from "@/recordPage";
import type { UseFormLayout } from "@/recordPage/formLayoutSource/useFormLayout";
import { routeFor } from "@/router/routeFor";
import RecordHeader from "./record/RecordHeader.vue";
import PageDialogs from "./record/dialogs/PageDialogs.vue";
import { formTabMemory } from "./record/formTabMemory";
import { fetchMeta } from "./record/metaSource";
import { PANEL_BUILTINS } from "./record/panel/builtins";
import { quickActionBuiltins } from "./record/quickActionBuiltins";
import { personOf, type DocInfo } from "./record/panel/context";
import { useDisclosure } from "./record/panel/disclosure";
import { layoutItems, layoutSections } from "./record/panel/panelEntries";
import RecordPanel from "./record/panel/RecordPanel.vue";
import {
	changedFields,
	conflictError,
	isTimestampMismatch,
	SAVE_CONFLICT,
	serverMessage,
} from "./record/saveResponse";
import PageFrame, { pageGutter } from "@/shell/PageFrame.vue";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const route = useRoute();
const router = useRouter();

const doc = ref<Record<string, any>>({});
const saved = ref<Record<string, any>>({});
const meta = ref<any>(null);
const docinfo = ref<DocInfo | null>(null);
const linkTitles = ref<Record<string, string>>({});
const error = ref("");
// Apart from `error`: a failed action must not blank the record (the form is in its v-else).
const actionError = ref("");
const controller = shallowRef<RecordPageController | null>(null);
// The doctype's Side Panel layout, or nothing: the panel never falls back to the Details layout.
const panelLayout = shallowRef<UseFormLayout | null>(null);
const detailsLayout = shallowRef<UseFormLayout | null>(null);
const actionsVersion = ref(0);
const saving = ref(false);
const formRoot = ref<HTMLElement | null>(null);
// The reader's intent and the strip's resolution, as `FormLayout` splits them.
const formTab = ref("");
const activeFormTab = ref("");

// The right zone keeps this many top-level controls; the rest demote into `⋯`.
const HEADER_BUDGET = 3;

// The slower of two in-flight loads must not win: `save()` would then POST the wrong record.
let generation = 0;

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
const docname = computed(() => String(route.params.name));

const dirty = computed(() => JSON.stringify(doc.value) !== JSON.stringify(saved.value));

const header = computed(() => {
	actionsVersion.value;
	const resolved = controller.value?.header.resolve() ?? [];
	return projectHeader(resolved, HEADER_BUDGET);
});

const form = computed(() => detailsLayout.value?.layout.value ?? []);

// Resolved against the draft, as the form's own `depends_on` is.
const sections = computed(() => layoutSections(panelLayout.value?.layout.value ?? [], doc.value));

// Open sections are the reader's, per doctype; the surface's labelled items are what there is to open.
const disclosure = useDisclosure(
	() => boot.user.name,
	() => `Record:${doctype.value}`,
	() =>
		(controller.value?.panelSections.visible() ?? [])
			.filter((item) => item.label)
			.map((item) => ({ name: item.name, opened: item.opened !== false }))
);

const tabMemory = computed(() => formTabMemory(boot.user.name, doctype.value ?? ""));

provide(LinkTitlesKey, linkTitles);

// One channel for the form and the panel, forwarded so it follows the controller across loads.
provide(CommitKey, {
	pending: (fieldname, value, row) => controller.value?.commits.pending(fieldname, value, row),
	commit: (fieldname, value, row) => controller.value?.commits.commit(fieldname, value, row),
	rowChanged: (row, change) => controller.value?.commits.rowChanged(row, change),
});

// The row's built-ins, re-read on every resolve so the title crumb tracks the draft.
function headerBuiltins(): HeaderItem[] {
	const title = doc.value[meta.value?.title_field] || docname.value;
	return [
		{
			name: "doctype",
			label: doctype.value ?? "",
			zone: "left",
			display: "crumb",
			href: router.resolve(routeFor(doctype.value!)).path,
		},
		{ name: "record", label: String(title), zone: "left", display: "crumb" },
		{ name: "save", label: "Save", display: "button", run: runSave },
	];
}

// Three built-ins first, then the Side Panel layout's sections, as they resolve now.
function panelBuiltins() {
	return [...PANEL_BUILTINS, ...layoutItems(sections.value)];
}

function chooseFormTab(identity: string) {
	formTab.value = identity;
	tabMemory.value.remember(identity);
}

/** `getdoc`: the document, its sidecar and the link titles in one round trip. */
async function fetchDoc(target: { doctype: string; name: string }) {
	const res = await fetch(
		`/api/method/frappe.desk.form.load.getdoc?${new URLSearchParams(target)}`
	);
	if (!res.ok) throw new Error(String(res.status));
	const body = await res.json();
	const document = body.docs?.[0];
	if (!document) throw new Error("404");
	return {
		document,
		docinfo: body.docinfo as DocInfo,
		linkTitles: (body._link_titles ?? {}) as Record<string, string>,
	};
}

async function load() {
	if (!doctype.value) return;
	const mine = ++generation;
	const target = { doctype: doctype.value, name: docname.value };
	error.value = "";
	const carriedActionError = actionError.value;

	// Blanked before the fetch: the heading changes synchronously, and the old controller's quick
	// actions close over the previous page. `saved` goes with `doc` so `isDirty` stays false.
	doc.value = {};
	saved.value = {};
	docinfo.value = null;
	controller.value = null;
	panelLayout.value = null;
	detailsLayout.value = null;
	disclosure.reset();
	formTab.value = tabMemory.value.recall();

	// Both layouts need only the doctype, so their fetches ride beside `getdoc` and the meta.
	// Against the saved document, so a keystroke cannot switch a layout under the reader.
	const details = useFormLayout({
		doctype: target.doctype,
		type: "Details",
		doc: saved,
		fallback: "meta",
		overrides: () => controller.value?.fields.resolve() ?? {},
		tabOverrides: () => controller.value?.formTabs.resolve() ?? {},
	});
	const panel = useFormLayout({
		doctype: target.doctype,
		type: "Side Panel",
		doc: saved,
		fallback: "none",
		overrides: () => controller.value?.fields.resolve() ?? {},
	});
	try {
		const [loaded, metadata] = await Promise.all([
			fetchDoc(target),
			fetchMeta(target.doctype),
		]);
		if (mine !== generation) return;
		saved.value = { ...loaded.document };
		doc.value = JSON.parse(JSON.stringify(loaded.document));
		docinfo.value = loaded.docinfo;
		linkTitles.value = loaded.linkTitles;
		meta.value = metadata;
	} catch (e) {
		if (mine !== generation) return;
		error.value =
			String(e) === "Error: 403"
				? "You do not have permission to read this record."
				: "Not found.";
		return;
	}

	const created = createRecordPage({
		doctype: target.doctype,
		docname: target.name,
		doc,
		saved,
		meta,
		perms: () => docinfo.value?.permissions ?? {},
		isDirty: () => dirty.value,
		// No tab strip on this page, so activation is a no-op.
		activeTab: () => "",
		activateTab: () => {},
		formLayout: () => form.value,
		activeFormTab: () => activeFormTab.value,
		activateFormTab: (identity) => void (formTab.value = identity),
		discloseSection: disclosure.disclose,
		focusField: (fieldname, cursor) => void landOn(fieldname, cursor),
		save: write,
		reload: load,
		router,
		sourcesReady: () => loadClientScripts(target.doctype),
	});
	created.header.provideBuiltins(headerBuiltins);
	created.quickActions.provideBuiltins(() =>
		quickActionBuiltins(docinfo.value?.permissions ?? {})
	);
	created.panelSections.provideBuiltins(panelBuiltins);
	panelLayout.value = panel;
	detailsLayout.value = details;
	controller.value = created;

	// The first replay must see both layouts, or a script's act on a tab or section is dropped as unknown.
	await Promise.all([details.settled(), panel.settled()]);
	if (mine !== generation) return;
	await created.refresh();
	if (mine !== generation) return;
	// A reload triggered by a failed action must not wipe the message explaining it.
	actionError.value = carriedActionError;
	actionsVersion.value++;
}

// One request at a time: a `page.save()` that lands mid-flight awaits the one in flight.
let inFlight: Promise<void> | null = null;

async function write() {
	// Refuse to write the wrong record if the route moved while an action ran.
	if (doc.value.name !== docname.value || doctype.value === null) {
		throw new Error("The record changed while saving; nothing was written.");
	}
	if (!inFlight) inFlight = send().finally(() => (inFlight = null));
	await inFlight;
}

async function send() {
	const mine = generation;
	saving.value = true;
	try {
		const res = await fetch("/api/method/frappe.client.save", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": boot.csrf_token,
			},
			body: JSON.stringify({ doc: { ...doc.value, doctype: doctype.value } }),
		});
		const body = await res.json().catch(() => null);
		if (!res.ok) {
			if (isTimestampMismatch(body)) {
				await resolveConflict();
				throw conflictError();
			}
			throw new Error(serverMessage(body) ?? `Save failed with ${res.status}`);
		}

		const document = body.message;
		if (mine !== generation) return;
		saved.value = { ...document };
		doc.value = JSON.parse(JSON.stringify(document));
	} finally {
		saving.value = false;
	}
	await controller.value?.refresh();
	actionsVersion.value++;
}

// Nothing is re-applied: the reader sees who saved and what they changed, and chooses.
async function resolveConflict() {
	const target = { doctype: doctype.value!, name: docname.value };
	const latest = await fetchDoc(target).catch(() => null);
	const editor = latest
		? personOf(latest.docinfo, latest.document.modified_by).name
		: "Someone else";
	const changed = changedFields(doc.value, saved.value, meta.value?.fields);
	const mine = changed.length ? `your changes to ${changed.join(", ")}` : "your changes";
	const reload = await controller.value!.page.dialog.confirm({
		title: "Saved by someone else",
		message: `${editor} saved this record after you opened it, so ${mine} cannot be saved over theirs. Reload to see their version, or keep editing to copy your values out first.`,
		confirmLabel: "Reload and lose my changes",
		cancelLabel: "Keep editing",
	});
	if (reload) await load();
}

// Not through `runAction`: a failed save must keep the draft on screen, not reload over it.
async function runSave() {
	actionError.value = "";
	try {
		await controller.value?.page.save();
	} catch (e) {
		if ((e as Error)?.name !== SAVE_CONFLICT) actionError.value = errorMessage(e);
	}
}

async function runAction(action: QuickAction | HeaderItem) {
	// Awaited and caught: a failing action would otherwise leave the draft mutated on screen
	// with no error. Reloading discards the rejected draft.
	actionError.value = "";
	try {
		await action.run?.(controller.value!.page);
	} catch (e) {
		actionError.value = errorMessage(e);
		await load();
	}
}

/** The host's half of `page.fields.focus`: the field's tab, then the scroll, then the cursor. */
async function landOn(fieldname: string, cursor: boolean) {
	const tab = identifyTabs(form.value).find((one) =>
		one.sections.some((section) =>
			section.columns.some((column) =>
				column.fields.some((field) => field.fieldname === fieldname)
			)
		)
	);
	if (tab) formTab.value = tab.identity;
	// The strip mounts a tab's panel a frame after the model moves, so the cell is polled for.
	for (let frame = 0; frame < 10; frame++) {
		await nextTick();
		const cell = formRoot.value?.querySelector<HTMLElement>(
			`.field[data-fieldname="${fieldname}"]`
		);
		if (cell) {
			cell.scrollIntoView({ block: "center" });
			if (cursor)
				cell.querySelector<HTMLElement>("input, textarea, select, button")?.focus();
			return;
		}
		await new Promise(requestAnimationFrame);
	}
}

function expand(field: FieldNode) {
	controller.value?.page.fields.focus(field.fieldname);
}

async function confirmLeave() {
	if (!dirty.value || !controller.value) return true;
	const discard = await controller.value.page.dialog.confirm({
		title: "Discard unsaved changes?",
		message: "This record has changes that are not saved.",
		confirmLabel: "Discard",
		cancelLabel: "Keep editing",
	});
	return !!discard;
}

onBeforeRouteLeave(confirmLeave);
onBeforeRouteUpdate((to, from) =>
	to.params.doctype === from.params.doctype && to.params.name === from.params.name
		? true
		: confirmLeave()
);

function onBeforeUnload(event: BeforeUnloadEvent) {
	if (!dirty.value) return;
	event.preventDefault();
}

// A key press is a deliberate gesture, so a clean doc answers with the button's own tooltip text.
function onKeydown(event: KeyboardEvent) {
	if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "s") return;
	event.preventDefault();
	if (!controller.value) return;
	if (!dirty.value) toast.info("No changes to save");
	runSave();
}

onMounted(() => {
	window.addEventListener("keydown", onKeydown);
	window.addEventListener("beforeunload", onBeforeUnload);
});
onUnmounted(() => {
	window.removeEventListener("keydown", onKeydown);
	window.removeEventListener("beforeunload", onBeforeUnload);
});

watch([doctype, docname], load, { immediate: true });
</script>
