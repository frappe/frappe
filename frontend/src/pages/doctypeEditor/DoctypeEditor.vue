<!-- The DocType editor at `/doctype/<name>`: one DocType in Design or Customize, with the pending
     edits a save sends. `/doctype/new` asks four questions first and edits a DocType not yet saved. -->
<template>
	<PageFrame :scroll="false" :state="pageState">
		<template v-if="state" #header>
			<EditorHeader
				v-model:tab="tab"
				:doctype="state.doctype"
				:canvas="layoutCanvas"
				:dirty="dirty"
				:can-undo="edits.canUndo.value"
				:can-redo="edits.canRedo.value"
				:can-save="canSave({ canvas: () => canvas, edits, save })"
				:saving="save.saving.value"
				:mode="state.mode"
				:modes="state.modes"
				v-model:finder-open="finderOpen"
				:developer-mode="boot.developer_mode"
				:finder="finder"
				:draft="Boolean(state.pending || openChild?.state.pending)"
				:child-crumbs="child.crumbs.value"
				@open-parent="child.open(null)"
				@act="(name, value) => acts.perform(name, value)"
			/>
		</template>
		<div
			v-if="!state"
			class="flex flex-1 items-center justify-center text-base text-ink-gray-5"
		>
			{{ __("Loading {0}…", [name]) }}
		</div>
		<template v-else-if="state">
			<div
				class="flex flex-1 items-center justify-center px-6 text-center text-base text-ink-gray-6 lg:hidden"
			>
				{{ __("The editor needs a wider window, 1024px or more.") }}
			</div>
			<div
				class="hidden min-h-0 flex-1 lg:flex"
				:inert="save.saving.value"
				data-doctype-editor
			>
				<ScrollArea class="flex min-h-0 min-w-0 flex-1" :viewport-class="pageGutter">
					<EditorCanvas
						v-if="tab === 'editor' && shown"
						:canvas="shown"
						:save="save"
						:customize="customizeRoute"
						:table="childTable"
					/>
					<SettingsTab
						v-else-if="tab === 'settings' && shown"
						:key="shown.state.doctype"
						v-model:place="settingsPlace"
						:canvas="shown"
						:customize="customizeRoute"
						:danger="dangerScope"
					/>
					<RowDialogPreview
						v-else-if="openChild"
						:canvas="openChild.canvas"
						:table-label="child.tableLabel.value"
					/>
					<PreviewTab
						v-else-if="!state.pending"
						:doctype="state.doctype"
						:record="previewName"
						:latest="latest"
						:title-field="String(state.definition.title_field ?? '')"
						@pick="previewName = $event"
					/>
					<p v-else class="py-6 text-base text-ink-gray-5">
						{{ __("Save the DocType to preview its records.") }}
					</p>
				</ScrollArea>
				<EditorPanel v-if="tab === 'editor' && shown?.editable" :canvas="shown" />
			</div>
		</template>
	</PageFrame>
</template>

<script setup lang="ts">
import {
	computed,
	defineAsyncComponent,
	inject,
	nextTick,
	onBeforeUnmount,
	reactive,
	ref,
	shallowRef,
	watch,
} from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import { ScrollArea, toast } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { getSocketInstance } from "@framework/ui/socket";
import { acts } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import { __, __n } from "@/i18n";
import { COPY_OF } from "@/newRecordValues";
import { discardChanges } from "@/pages/record/discardChanges";
import { errorMessage } from "@/recordPage/errorMessage";
import { canRoute, routeFor } from "@/router/routeFor";
import { shellDialog } from "@/shell/dialog";
import PageFrame, { pageGutter } from "@/shell/PageFrame.vue";
import { failedState, type PageStateValue } from "@/shell/pageState";
import { useUnloadGuard } from "@/unloadGuard";
import EditorCanvas from "./EditorCanvas.vue";
import EditorHeader from "./EditorHeader.vue";
import type { FinderHost } from "./editorFinder";
import EditorPanel from "./EditorPanel.vue";
import { customizeHost } from "./customizeHost";
import { dangerHost } from "./dangerHost";
import { DesignCanvas } from "./designCanvas";
import { ForkWarning } from "./forkWarning";
import { LatestWins, type Current } from "./latestWins";
import { openFromAddress, useLayoutAddress } from "./layoutQuery";
import { canSave, useEditorActs } from "./editorActs";
import { EditorSave, type ExportResult } from "./editorSave";
import {
	carriedAnswers,
	completeAnswers,
	copiedAnswers,
	holdsRoute,
	loadEditor,
	modeOf,
	pendingDoctype,
	type EditorState,
} from "./editorSource";
import { lastModule } from "./lastModule";
import { askNewDoctype } from "./newDoctypeFlow";
import {
	PendingEdits,
	type EditorMode,
	type EditorTab,
	type PendingEditsPayload,
} from "./pendingEdits";
import PreviewTab from "./PreviewTab.vue";
import { confirmModeSwitch, guardRouteUpdate } from "./modeSwitch";
import ModeSwitchDialog from "./ModeSwitchDialog.vue";
import RowDialogPreview from "./RowDialogPreview.vue";
import { SETTING_ROWS } from "./settingsRows";
import type { SettingsPlace } from "./settingsView";
import { useChildTables } from "./useChildTables";

const SettingsTab = defineAsyncComponent(() => import("./SettingsTab.vue"));

const route = useRoute();
const router = useRouter();
const boot = inject<Boot>("boot")!;
const name = computed(() => String(route.params.name));

const state = shallowRef<EditorState | null>(null);
const canvas = shallowRef<DesignCanvas | null>(null);
const forks = new ForkWarning(async (type, working) => {
	const { confirmFork } = await import("./layoutDialogs");
	return confirmFork(working, type);
});
const pageState = shallowRef<PageStateValue | null>(null);
const tab = ref<EditorTab>("editor");
const settingsPlace = ref<SettingsPlace>({ section: "", found: null });
const previewName = ref<string | null>(null);
const finderOpen = ref(false);
const latest = ref<string[]>([]);

// Filled when the load lands; the payload reads it then.
const head = reactive({}) as Omit<PendingEditsPayload, "edits">;
const edits = new PendingEdits(head, (opened, doctype) => {
	tab.value = opened;
	child.reopen(doctype);
});
const child = useChildTables(edits, () => canvas.value, forks);
const childTable = computed(() => {
	const field = canvas.value?.working.value.fields.find(
		(one) => one.fieldname === openChild.value?.table
	);
	return field && canvas.value ? { field, parent: canvas.value.state.doctype } : null;
});
const { session: openChild, shown } = child;
// A child's editor opens at its own top, not at the parent's scroll position.
watch(shown, () =>
	nextTick(() =>
		document
			.querySelector("[data-doctype-editor] [data-reka-scroll-area-viewport]")
			?.scrollTo(0, 0)
	)
);
const layoutCanvas = computed(() => (openChild.value?.state.pending ? null : shown.value));
const save = new EditorSave({
	edits,
	canvas: () => canvas.value,
	reload,
	created,
	children: child.tables,
	showChild: child.showChild,
	findSetting,
});
// The latest load wins; it also ends with the page, so a Danger zone act still running skips its follow-up.
const loads = new LatestWins();

useEditorActs({
	edits,
	tab,
	canvas: () => shown.value,
	toggleFinder: () => (finderOpen.value = !finderOpen.value),
	previewRecord: (record) => (previewName.value = record),
	save,
	openList,
	openChild: child.open,
	customize: customizeHost({
		dirty: () => dirty.value,
		developerMode: boot.developer_mode,
		setMode: (mode) => router.push({ query: { ...route.query, mode: mode.toLowerCase() } }),
		reload,
	}),
	danger: dangerHost({
		scope: () => dangerScope.value,
		dirty: () => dirty.value,
		save: saveFirst,
		discard: () => edits.clear(),
		reload,
		// The new name opens as a first save's does: loaded, then the address follows.
		renamed: created,
		// Each act settles pending edits first, so the leave guard has nothing to ask.
		deleted: () => router.push(routeFor("DocType")),
		// Another DocType or page since the act began: its follow-up must not pull the reader back.
		showing: (doctype) => !loads.isStopped && state.value?.doctype === doctype,
	}),
	recordOptions: async (query) =>
		[null, ...latest.value]
			.filter(
				(record) => !query || (record ?? "").toLowerCase().includes(query.toLowerCase())
			)
			.map((record) => ({ value: record, label: record ?? __("Empty form") })),
});

// The Danger zone acts on the page's DocType, not on a child table opened from it.
const dangerScope = computed(() =>
	openChild.value
		? null
		: {
				developerMode: boot.developer_mode,
				administrator: boot.session.user.name === "Administrator",
		  }
);
// Getters: the finder reads them once it opens.
const finder: FinderHost = {
	get canvas() {
		return shown.value;
	},
	get scope() {
		return dangerScope.value;
	},
	get panelShown() {
		return tab.value === "editor";
	},
	find,
	findSetting,
};
// A new DocType is not saved until its first save, even with no edits staged.
const dirty = computed(() => edits.dirty.value || Boolean(state.value?.pending));

const customizeRoute = computed(() =>
	state.value?.modes.includes("Customize")
		? { query: { ...route.query, mode: "customize" } }
		: null
);

watch([name, () => route.query.mode, () => route.query[COPY_OF]], load, { immediate: true });
useLayoutAddress(() => canvas.value);

async function load() {
	const mode = modeOf(route.query.mode);
	// Unsaved edits, or a DocType not yet saved, still load: a discarded switch must clear them.
	if (!dirty.value && holdsRoute(state.value, name.value, mode)) return;
	const current = loads.begin();
	reset();
	if (name.value === "new") return void startAsking(current);
	try {
		const loaded = await loadEditor(name.value, mode);
		if (!current()) return;
		open(loaded);
		loadLatest(loaded, current).catch(() => (latest.value = []));
	} catch (error) {
		if (current()) pageState.value = failedState(error, load);
	}
}

async function startAsking(current: Current) {
	const { answers, copyOf } = carriedAnswers(route.query);
	let source: EditorState | null = null;
	if (copyOf) {
		try {
			source = await loadEditor(copyOf, "Design");
		} catch (error) {
			if (!current()) return;
			// No source to copy: a blank draft would pass for the copy.
			toast.error(errorMessage(error));
			return void router.replace(routeFor("DocType"));
		}
	}
	if (!current()) return;
	const first = { ...(source && copiedAnswers(source)), ...answers };
	const complete = completeAnswers(first);
	if (!complete) return void askNewDoctype(router, first, copyOf, boot.session.user.name);
	open(pendingDoctype(complete, source));
}

function reset() {
	state.value = null;
	canvas.value = null;
	child.tables.reset();
	pageState.value = null;
	tab.value = "editor";
	latest.value = [];
	previewName.value = null;
	edits.clear();
	if (save.banner.value?.doctype !== name.value) save.banner.value = null;
}

async function reload(): Promise<DesignCanvas | null> {
	const { doctype, mode } = state.value!;
	const loaded = await loadFor(loads.begin(), doctype, mode);
	if (!loaded) return null;
	edits.clear();
	open(loaded);
	return canvas.value!;
}

async function created(doctype: string): Promise<DesignCanvas | null> {
	// A rename opens through here too; only a draft's first save names the module last used.
	const firstSave = Boolean(state.value?.pending);
	const loaded = await loadFor(loads.begin(), doctype, "Design");
	if (!loaded) return null;
	if (firstSave) lastModule(boot.session.user.name).remember(loaded.module);
	edits.clear();
	open(loaded);
	await router.replace(routeFor("DocType", doctype));
	return canvas.value!;
}

/** Loads for the editor open now; null once the page moved on to another DocType or mode, or was left. */
async function loadFor(current: Current, doctype: string, mode: EditorMode) {
	try {
		const loaded = await loadEditor(doctype, mode);
		return current() ? loaded : null;
	} catch (error) {
		if (current()) throw error;
		return null;
	}
}

function openList() {
	const doctype = state.value!.doctype;
	if (canRoute(doctype)) return void router.push(routeFor(doctype));
	// The tab's address table predates this DocType: a full load reads a fresh one, and the
	// router finds the list by the DocType's name.
	window.location.assign(router.resolve({ name: "list", params: { doctype } }).href);
}

function open(loaded: EditorState) {
	Object.assign(head, {
		doctype: loaded.doctype,
		mode: loaded.mode,
		base_version: loaded.base_version,
	});
	state.value = loaded;
	child.tables.reset();
	canvas.value = new DesignCanvas(loaded, edits, forks);
	openFromAddress(canvas.value, route.query);
}

function find(fieldname: string) {
	tab.value = "editor";
	const open = shown.value;
	if (!open) return;
	open.select({ kind: "field", fieldname });
	if (!open.place(fieldname)) open.trayOpen.value = true;
}

function findSetting(key: string) {
	const row = canvas.value && SETTING_ROWS.find((one) => one.key === key);
	if (!row) return;
	tab.value = "settings";
	settingsPlace.value = { section: row.section, found: { key, at: Date.now() } };
}

async function loadLatest(loaded: EditorState, current: Current) {
	const { issingle, istable } = loaded.definition;
	if (issingle || istable || !loaded.record_count) return;
	const { data } = await listDocuments<{ name: string }>(loaded.doctype, {
		fields: ["name"],
		order_by: "modified desc",
		limit: 20,
	});
	if (!current()) return;
	latest.value = data.map((row) => String(row.name));
	previewName.value = latest.value[0] ?? null;
}

async function confirmLeave() {
	if (!dirty.value) return true;
	return discardChanges(
		shellDialog().confirm,
		__("This DocType has changes that are not saved.")
	);
}

function confirmSwitch() {
	return confirmModeSwitch({
		dirty: dirty.value,
		ask: () =>
			shellDialog().open(
				ModeSwitchDialog,
				{ message: __("This DocType has changes that are not saved.") },
				{ title: __("Save before you switch?") }
			),
		save: saveFirst,
	});
}

async function saveFirst() {
	await save.save();
	return !dirty.value;
}

const socket = getSocketInstance();
const onExport = (...args: unknown[]) =>
	save.exported(args[0] as ExportResult).catch((error) => toast.error(errorMessage(error)));
socket?.on("doctype_export", onExport);
onBeforeUnmount(() => {
	loads.stop();
	socket?.off("doctype_export", onExport);
});

onBeforeRouteLeave(confirmLeave);
onBeforeRouteUpdate((to, from) =>
	guardRouteUpdate(to, from, { leave: confirmLeave, switchMode: confirmSwitch })
);
useUnloadGuard(() => dirty.value);
</script>
