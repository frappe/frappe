<!--
  The generated record page every app gets at /apps/<prefix>/<slug>/<name>: a host for the
  record-page engine with a header row, the Details form, the panel and its own scroll.
-->
<template>
	<PageFrame :scroll="false">
		<template v-if="controller" #aboveHeader>
			<FrameBands :bands="frame.before" :page="controller.page" />
		</template>

		<!-- No slot when a script emptied or hid the row: the frame then draws no row at all. -->
		<template
			v-if="doctype && frame.header && (!controller || !isEmptyHeader(header))"
			#header
		>
			<RecordHeader
				v-if="controller"
				:projection="header"
				:page="controller.page"
				:dirty="dirty"
				:saving="saving"
				:favourites="favourites"
				:favourited="favourited"
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

		<FrameBands v-else-if="controller" :bands="frame.between" :page="controller.page" />

		<template v-if="doctype && frame.body">
			<p v-if="error" class="py-5 text-sm text-ink-red-4" :class="pageGutter">
				{{ error }}
			</p>

			<BodyColumns
				v-else-if="controller"
				:items="bodyItems"
				:page="controller.page"
				:user="boot.user.name"
			>
				<template #form>
					<div ref="formRoot" data-record-form>
						<FormLayout
							v-if="form.length"
							v-model:doc="doc"
							:layout="form"
							:tab="formTab"
							:class="formClasses"
							@update:tab="chooseFormTab"
							@update:activeTab="activeFormTab = $event"
						/>
					</div>
				</template>

				<template #panel="{ collapsed }">
					<RecordPanel
						v-model:doc="doc"
						:doctype="doctype"
						:docname="docname"
						:controller="controller"
						:meta="meta"
						:docinfo="docinfo"
						:sections="sections"
						:disclosure="disclosure"
						:collapsed="collapsed"
						:run="runAction"
						:reloadDocinfo="reloadDocinfo"
						@expand="expand"
					/>
				</template>
			</BodyColumns>
		</template>

		<FrameBands v-if="controller" :bands="frame.after" :page="controller.page" />

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
import { toast } from "frappe-ui";
import { isApiError } from "@framework/ui/api";
import { FormLayout } from "@framework/ui/components/FormLayout";
import { CommitKey, LinkTitlesKey } from "@framework/ui/components/Fields/types";
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import { identifyTabs } from "@framework/ui/components/FormLayout/tabIdentity";
import { getSocketInstance } from "@framework/ui/socket";
import {
	createRecordPage,
	errorMessage,
	formItems,
	isEmptyHeader,
	joinForm,
	loadClientScripts,
	projectFrame,
	projectHeader,
	SAVE_VETO,
	useFormLayout,
	type HeaderItem,
	type QuickAction,
	type RecordPageApi,
	type RecordPageController,
} from "@/recordPage";
import type { UseFormLayout } from "@/recordPage/formLayoutSource/useFormLayout";
import { routeFor } from "@/router/routeFor";
import BodyColumns from "./record/body/BodyColumns.vue";
import FrameBands from "./record/FrameBands.vue";
import RecordHeader from "./record/RecordHeader.vue";
import PageDialogs from "./record/dialogs/PageDialogs.vue";
import { formTabMemory } from "./record/formTabMemory";
import { fetchMeta } from "./record/metaSource";
import { PANEL_BUILTINS } from "./record/panel/builtins";
import { headerMenuBuiltins, quickActionBuiltins } from "./record/builtinActions";
import { favouritesOf, hasFavourited } from "./record/favourites";
import { useLiveDocinfo } from "./record/liveDocinfo";
import { useLiveClientScripts } from "./record/liveClientScripts";
import { personOf, type DocInfo } from "./record/panel/context";
import { tagsOf } from "./record/panel/people";
import { useDisclosure } from "./record/panel/disclosure";
import { layoutItems, layoutSections } from "./record/panel/panelEntries";
import RecordPanel from "./record/panel/RecordPanel.vue";
import { loadParts, loadRecord, saveRecord } from "./record/recordSource";
import { changedFields, conflictError, SAVE_CONFLICT, stripTags } from "./record/saveResponse";
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

// The form fills the column with no border of its own, and its strip stays put while the sections scroll.
// The strip and the sections share the header row's gutter, so the fields line up with the crumbs.
const formClasses = [
	"!rounded-none !border-0",
	"[&_[role='tablist']]:sticky [&_[role='tablist']]:top-0 [&_[role='tablist']]:z-10 [&_[role='tablist']]:bg-surface-base",
	"[&_[role='tablist']]:gap-5 [&_[role='tablist']]:px-[--page-gutter] [&_[role='tablist']]:py-2 [&_[role='tab']]:rounded-4",
	"[&_.sections]:mx-auto [&_.sections]:my-0 [&_.sections]:w-full [&_.sections]:max-w-3xl [&_.sections]:px-[--page-gutter] [&_.sections]:py-6",
	"[&_.section-header]:!px-0 [&_.section-body]:!px-0",
];

// The right zone keeps this many top-level controls; the rest demote into `⋯`.
const HEADER_BUDGET = 3;
// Save keeps its slot whatever a script adds; it is the only pinned control.
const PINNED_CONTROLS = ["save"];

// The slower of two in-flight loads must not win: `save()` would then POST the wrong record.
let generation = 0;
// Likewise for two sidecar re-reads: several picks in one gesture each fire one.
let docinfoRead = 0;

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
const docname = computed(() => String(route.params.name));

const dirty = computed(() => JSON.stringify(doc.value) !== JSON.stringify(saved.value));

// Off the sidecar, like the people rows: a favourite is never part of the draft.
const favourites = computed(() => favouritesOf(docinfo.value, boot.user.name));
const favourited = computed(() => hasFavourited(docinfo.value, boot.user.name));

const header = computed(() => {
	actionsVersion.value;
	const resolved = controller.value?.header.resolve() ?? [];
	return projectHeader(resolved, HEADER_BUDGET, PINNED_CONTROLS);
});

const frame = computed(() => {
	actionsVersion.value;
	return projectFrame(controller.value?.frame.resolve() ?? []);
});

// A panel with every section hidden draws nothing, on the header's precedent: the form takes the width.
const panelShown = computed(() => {
	actionsVersion.value;
	return (controller.value?.panelSections.visible().length ?? 0) > 0;
});

const bodyItems = computed(() => {
	actionsVersion.value;
	const items = controller.value?.body.visible() ?? [];
	return items.filter((item) => item.name !== "panel" || panelShown.value);
});

// The layout as the source joins it, then as `page.form` arranges it.
const detailsForm = computed(() => detailsLayout.value?.layout.value ?? []);
const form = computed(() => {
	actionsVersion.value;
	const page = controller.value;
	return page ? joinForm(detailsForm.value, page.form.resolve(), page.page) : detailsForm.value;
});

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

// The record's realtime room, joined per load; the panel's rows follow another tab's assign or comment.
const live = useLiveDocinfo({ socket: getSocketInstance(), docinfo, reload: reloadDocinfo });
useLiveClientScripts({
	doctype,
	dirty: () => dirty.value,
	ready: () => controller.value?.ready.value ?? false,
	refresh: () => controller.value?.refresh(),
});

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
	const single = addresses.isSingle(doctype.value!);
	const items: HeaderItem[] = [
		// A single is its own list: one crumb, no link.
		{
			name: "doctype",
			label: doctype.value ?? "",
			zone: "left",
			display: "crumb",
			href: single ? undefined : router.resolve(routeFor(doctype.value!)).path,
		},
	];
	if (!single)
		items.push({ name: "record", label: String(title), zone: "left", display: "crumb" });
	items.push(
		{
			name: "favourite",
			label: "Favourite",
			icon: "lucide-star",
			zone: "left",
			display: "button",
			run: toggleFavourite,
		},
		{ name: "save", label: "Save", display: "button", run: runSave },
		...headerMenuBuiltins(
			docinfo.value?.permissions ?? {},
			{ favourited: favourited.value, toggle: toggleFavourite },
			{ single }
		)
	);
	return items;
}

// The answer is discarded and the sidecar re-read, as the people rows do, so the star never
// disagrees with the server. A failure toasts here: `runAction` would otherwise reload over the draft.
// Clicks queue: each one reads the state the one before it left, so two quick clicks toggle twice.
let favouriteTurn: Promise<void> = Promise.resolve();

function toggleFavourite(page: RecordPageApi) {
	favouriteTurn = favouriteTurn.then(async () => {
		// A turn that outlived its record would read the next record's state; it does nothing.
		if (page.doctype !== doctype.value || page.docname !== docname.value) return;
		try {
			await page.call("frappe.desk.doctype.favourite.favourite.toggle_favourite", {
				doctype: page.doctype,
				name: page.docname,
				add: !favourited.value,
			});
			await reloadDocinfo();
		} catch (e) {
			toast.error(errorMessage(e));
		}
	});
	return favouriteTurn;
}

// Three built-ins first, then the Side Panel layout's sections, as they resolve now.
function panelBuiltins() {
	return [...PANEL_BUILTINS, ...layoutItems(sections.value)];
}

function chooseFormTab(identity: string) {
	formTab.value = identity;
	tabMemory.value.remember(identity);
}

async function reloadDocinfo() {
	if (!doctype.value) return;
	const mine = generation;
	const read = ++docinfoRead;
	const fresh = await loadParts(doctype.value, docname.value);
	if (mine !== generation || read !== docinfoRead) return;
	docinfo.value = fresh;
}

async function load() {
	if (!doctype.value) {
		live.release();
		return;
	}
	const mine = ++generation;
	docinfoRead++;
	const target = { doctype: doctype.value, name: docname.value };
	error.value = "";
	live.follow(target.doctype, target.name);

	// Blanked before the fetch: the heading changes synchronously, and the old controller's quick
	// actions close over the previous page. `saved` goes with `doc` so `isDirty` stays false.
	doc.value = {};
	saved.value = {};
	docinfo.value = null;
	linkTitles.value = {};
	saving.value = false;
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
		tabOverrides: () => controller.value?.form.tabs.resolve() ?? {},
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
			loadRecord(target.doctype, target.name),
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
			isApiError(e) && e.status === 403
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
		formLayout: () => detailsForm.value,
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
		quickActionBuiltins(docinfo.value?.permissions ?? {}, tagsOf(docinfo.value).length > 0)
	);
	created.panelSections.provideBuiltins(panelBuiltins);
	created.form.provideBuiltins(() => formItems(detailsForm.value));
	panelLayout.value = panel;
	detailsLayout.value = details;
	controller.value = created;

	// The first replay must see both layouts, or a script's act on a tab or section is dropped as unknown.
	await Promise.all([details.settled(), panel.settled()]);
	if (mine !== generation) return;
	await created.refresh();
	if (mine !== generation) return;
	actionsVersion.value++;
}

// One request per record at a time; a request the previous record left in flight is not joined.
let inFlight: { generation: number; request: Promise<void> } | null = null;

async function write() {
	// Refuse to write the wrong record if the route moved while an action ran.
	if (doc.value.name !== docname.value || doctype.value === null) {
		throw new Error("The record changed while saving; nothing was written.");
	}
	if (inFlight?.generation !== generation) {
		const mine = generation;
		const request = send().finally(() => {
			if (inFlight?.request === request) inFlight = null;
		});
		inFlight = { generation: mine, request };
	}
	await inFlight.request;
}

async function send() {
	const mine = generation;
	saving.value = true;
	try {
		const document = await saveRecord(doctype.value!, doc.value).catch(rethrowSaveError);
		if (mine !== generation) return;
		saved.value = { ...document };
		doc.value = JSON.parse(JSON.stringify(document));
	} finally {
		// A request the previous record left behind must not clear this record's flag.
		if (mine === generation) saving.value = false;
	}
	// A save writes a version row and its hooks may assign.
	live.reloadQuietly();
	await controller.value?.refresh();
	actionsVersion.value++;
}

// A conflict is resolved with the reader; any other refusal reads as text, since a msgprint is often HTML.
async function rethrowSaveError(e: unknown): Promise<never> {
	if (isApiError(e) && e.isTimestampMismatch) {
		saving.value = false;
		await resolveConflict();
		throw conflictError();
	}
	throw isApiError(e) ? new Error(stripTags(e.message)) : e;
}

// Nothing is re-applied: the reader sees who saved and what they changed, and chooses.
async function resolveConflict() {
	const latest = await loadRecord(doctype.value!, docname.value).catch(() => null);
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
	try {
		await controller.value?.page.save();
	} catch (e) {
		if ((e as Error)?.name !== SAVE_CONFLICT) toast.error(errorMessage(e));
	}
}

// A failing action would otherwise leave the draft mutated with no error, so it reloads;
// a save the reader vetoed or must resolve keeps the draft, as the built-in Save does.
async function runAction(action: QuickAction | HeaderItem) {
	try {
		await action.run?.(controller.value!.page);
	} catch (e) {
		const name = (e as Error)?.name;
		if (name === SAVE_CONFLICT) return;
		toast.error(errorMessage(e));
		if (name !== SAVE_VETO) await load();
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
	if (import.meta.env.DEV)
		console.warn(
			`[record-page] page.fields.focus("${fieldname}") — not on the form; the reader was not moved.`
		);
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
	if (!controller.value || event.repeat) return;
	if (!dirty.value) toast.info("No changes to save");
	runSave();
}

onMounted(() => {
	window.addEventListener("keydown", onKeydown);
	window.addEventListener("beforeunload", onBeforeUnload);
});
onUnmounted(() => {
	live.dispose();
	window.removeEventListener("keydown", onKeydown);
	window.removeEventListener("beforeunload", onBeforeUnload);
});

watch([doctype, docname], load, { immediate: true });
</script>
