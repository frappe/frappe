<!--
  The generated record page every app gets at /apps/<prefix>/<slug>/<name>: a host for the
  record-page engine with a header row, the Details form, the panel and its own scroll.
-->
<template>
	<PageFrame :scroll="false">
		<template v-if="painted" #aboveHeader>
			<FrameBands :bands="frame.before" :page="painted.page" />
		</template>

		<!-- No slot when a script emptied or hid the row: the frame then draws no row at all. -->
		<template v-if="doctype && frame.header && (!painted || !isEmptyHeader(header))" #header>
			<RecordHeader
				v-if="painted"
				:projection="header"
				:page="painted.page"
				:dirty="dirty"
				:saving="painted.isSaving.value"
				:favourites="favourites"
				:favourited="favourited"
				@run="runAction"
			/>
			<div v-else-if="error" class="flex items-center gap-3">
				<h1 class="text-lg font-semibold">{{ route.params.name }}</h1>
				<span class="text-sm text-ink-gray-5">{{ doctype }}</span>
			</div>
			<HeaderSkeleton v-else />
		</template>

		<p v-if="!doctype" class="py-5 text-sm text-ink-gray-6" :class="pageGutter">
			No doctype is served at <code>{{ route.params.doctype }}</code> under this prefix.
		</p>

		<FrameBands v-else-if="painted" :bands="frame.between" :page="painted.page" />

		<template v-if="doctype && frame.body">
			<p v-if="error" class="py-5 text-sm text-ink-red-4" :class="pageGutter">
				{{ error }}
			</p>

			<!-- Keyed per record: a paint from memory patches in place, and would keep the last record's scroll. -->
			<BodyColumns
				v-else-if="painted"
				ref="body"
				:key="documentKey(painted.page.doctype, painted.page.docname)"
				:items="bodyItems"
				:page="painted.page"
				:user="boot.session.user.name"
			>
				<template #form>
					<RecordTabs
						:tabs="tabEntries"
						:active="shownTab"
						:page="painted.page"
						:claimsFocus="tabsHost.claimsFocus"
						@select="tabsHost.activate"
					>
						<template #details>
							<div ref="formRoot" data-record-form>
								<FormLayout
									v-if="form.length"
									v-model:doc="doc"
									v-model:sections="formSections"
									:layout="form"
									:tab="formTab"
									:class="formClasses"
									@update:tab="chooseFormTab"
									@update:activeTab="activeFormTab = $event"
								/>
							</div>
						</template>
						<template #composer>
							<RecordComposer
								:controller="painted"
								:tabs="stripTabs"
								:active="shownTab"
								:user="boot.session.user"
							/>
						</template>
					</RecordTabs>
				</template>

				<template #panel="{ collapsed }">
					<RecordPanel
						v-model:doc="doc"
						:doctype="doctype"
						:docname="docname"
						:controller="painted"
						:meta="meta"
						:docinfo="docinfo"
						:sections="sections"
						:layoutLoading="panelLoading"
						:disclosure="disclosure"
						:collapsed="collapsed"
						:run="runAction"
						:reloadDocinfo="reloadDocinfo"
						:whileOnRecord="visitCheck"
						@expand="expand"
					/>
				</template>
			</BodyColumns>

			<BodySkeleton
				v-else
				:user="boot.session.user.name"
				:feed="addressesFeed(openedQuery)"
			/>
		</template>

		<FrameBands v-if="painted" :bands="frame.after" :page="painted.page" />

		<PageDialogs v-if="controller" :controller="controller" />
		<RecordUploadDialog v-if="controller" :page="controller.page" />
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
import {
	onBeforeRouteLeave,
	onBeforeRouteUpdate,
	useRoute,
	useRouter,
	type LocationQuery,
} from "vue-router";
import { toast } from "frappe-ui";
import {
	addFavourite,
	addFollow,
	isApiError,
	removeFavourite,
	removeFollow,
	type Envelope,
} from "@framework/ui/api";
import { documentKey } from "@framework/ui/cache";
import { FormLayout } from "@framework/ui/components/FormLayout";
import { CommitKey, LinkTitlesKey } from "@framework/ui/components/Fields/types";
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import { identifyTabs } from "@framework/ui/components/FormLayout/tabIdentity";
import { getSocketInstance } from "@framework/ui/socket";
import { useDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { onScrollSettled } from "@framework/ui/utils/scrollLanding";
import { holdFresh } from "@framework/ui/utils/sharedState";
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
import { LATE_LIMIT_MS } from "@/recordPage/paintGate";
import { routeFor } from "@/router/routeFor";
import { __ } from "@/i18n";
import BodyColumns from "./record/body/BodyColumns.vue";
import FrameBands from "./record/FrameBands.vue";
import RecordHeader from "./record/RecordHeader.vue";
import RecordTabs from "./record/tabs/RecordTabs.vue";
import RecordComposer from "./record/composer/RecordComposer.vue";
import { composerBuiltins, composerHost } from "./record/composer/composerHost";
import { useComposerRecord } from "./record/composer/writerContext";
import { FILES_TAB, TAB_STRIP_CLASSES, recordTabBuiltins } from "./record/tabs/recordTabs";
import { useRecordTabs } from "./record/tabs/useRecordTabs";
import {
	activityPointer,
	addressesFeed,
	feedInMemory,
	RecordFeeds,
	RecordFeedsKey,
	withFeedRead,
} from "./record/feed/recordFeeds";
import PageDialogs from "./record/dialogs/PageDialogs.vue";
import RecordUploadDialog from "./record/feed/RecordUploadDialog.vue";
import { formTabMemory } from "./record/formTabMemory";
import { fetchMeta, metaInMemory } from "./record/metaSource";
import { PANEL_BUILTINS } from "./record/panel/builtins";
import { headerMenuBuiltins, quickActionBuiltins } from "./record/builtinActions";
import { favouritesOf, hasFavourited } from "./record/favourites";
import { canFollow, declinedMessage } from "./record/follow";
import { useLiveDocinfo, warnDocinfoFailed } from "./record/liveDocinfo";
import { useLiveClientScripts } from "./record/liveClientScripts";
import { personOf, type DocInfo } from "./record/panel/context";
import { mergePart } from "./record/panel/peopleActions";
import { tagsOf } from "./record/panel/people";
import { useDisclosure } from "./record/panel/disclosure";
import { layoutItems, layoutSections } from "./record/panel/panelEntries";
import RecordPanel from "./record/panel/RecordPanel.vue";
import BodySkeleton from "./record/skeletons/BodySkeleton.vue";
import HeaderSkeleton from "./record/skeletons/HeaderSkeleton.vue";
import {
	loadParts,
	loadRecord,
	readCachedRecord,
	saveRecord,
	type LoadedRecord,
} from "./record/recordSource";
import { mergeRefetch, same } from "./record/refetchMerge";
import { recallView, viewKeeper, type RecordView } from "./record/viewMemory";
import { Visit } from "./record/visit";
import { landOffsets, readOffsets } from "./record/viewScroll";
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
const painted = computed(() => (controller.value?.ready.value ? controller.value : null));
// The doctype's Side Panel layout, or nothing: the panel never falls back to the Details layout.
const panelLayout = shallowRef<UseFormLayout | null>(null);
const detailsLayout = shallowRef<UseFormLayout | null>(null);
const actionsVersion = ref(0);
const formRoot = ref<HTMLElement | null>(null);
// The reader's intent and the strip's resolution, as `FormLayout` splits them.
const formTab = ref("");
const activeFormTab = ref("");
const formSections = ref<Record<string, boolean>>({});
const body = ref<InstanceType<typeof BodyColumns> | null>(null);
const bodyRoot = computed(() => (body.value?.$el as HTMLElement | undefined) ?? null);
// The address this load opened with, a restored tab applied: the feed read and its placeholder follow it.
const openedQuery = shallowRef<LocationQuery>(route.query);
// Where this load's view is kept, and false until its restored view has landed, so a clamped scroll is not kept.
let keeper: ((view: RecordView) => void) | null = null;
let keeping = false;

// The form fills the column with no border of its own, and its strip stays put while the sections scroll.
// The strip and the sections share the header row's gutter, so the fields line up with the crumbs.
const formClasses = [
	"!rounded-none !border-0",
	"[&_[role='tablist']]:sticky [&_[role='tablist']]:top-0 [&_[role='tablist']]:z-10 [&_[role='tablist']]:bg-surface-base",
	TAB_STRIP_CLASSES,
	"[&_.sections]:mx-auto [&_.sections]:my-0 [&_.sections]:w-full [&_.sections]:max-w-3xl [&_.sections]:px-[--page-gutter] [&_.sections]:py-6",
	"[&_.section-header]:!px-0 [&_.section-body]:!px-0",
];

// The right zone keeps this many top-level controls; the rest demote into `⋯`.
const HEADER_BUDGET = 3;
// Save keeps its slot whatever a script adds; it is the only pinned control.
const PINNED_CONTROLS = ["save"];

let currentVisit = new Visit();
// A return visit's hold on fresh meta and layouts, let go with its background reads.
let releaseFresh = () => {};

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
const docname = computed(() => String(route.params.name));

const dirty = computed(() => JSON.stringify(doc.value) !== JSON.stringify(saved.value));

// Off the sidecar, like the people rows: a favourite is never part of the draft.
const favourites = computed(() => favouritesOf(docinfo.value, boot.session.user.name));
const favourited = computed(() => hasFavourited(docinfo.value, boot.session.user.name));
const following = computed(() => Boolean(docinfo.value?.follows));
// Absent while the gate is shut, so the built-ins seed no follow at all.
const follow = computed(() =>
	canFollow(meta.value, boot.session)
		? { following: following.value, toggle: toggleFollow }
		: undefined
);

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
const panelLoading = computed(() => panelLayout.value?.loading.value ?? false);

// Open sections are the reader's, per doctype; the surface's labelled items are what there is to open.
const disclosure = useDisclosure(
	() => boot.session.user.name,
	() => `Record:${doctype.value}`,
	() =>
		(controller.value?.panelSections.visible() ?? [])
			.filter((item) => item.label)
			.map((item) => ({ name: item.name, opened: item.opened !== false }))
);

const {
	host: tabsHost,
	entries: tabEntries,
	shown: shownTab,
	pageHost: tabsPageHost,
} = useRecordTabs({
	route,
	router,
	controller: () => controller.value,
	formTab: () => activeFormTab.value,
});

// What the composer band reads: the strip's tabs as drawn, in strip order.
const stripTabs = computed(() =>
	tabEntries.value.filter((entry) => !entry.hidden).map((entry) => entry.item)
);

const tabMemory = computed(() => formTabMemory(boot.session.user.name, doctype.value ?? ""));

const feeds = new RecordFeeds({
	docinfo,
	controller: () => controller.value,
	showTab: (name, what) => tabsHost.show(name, what),
	reloadParts: reloadDocinfo,
	whileOnRecord: visitCheck,
});
provide(RecordFeedsKey, feeds);
// Held for the page's life, so a script hiding the band leaves the writers their record.
useComposerRecord(() => controller.value, feeds);

// The record's realtime room, joined per load; the panel's rows follow another tab's assign or comment.
const live = useLiveDocinfo({ socket: getSocketInstance(), docinfo, reload: reloadDocinfo });
useLiveClientScripts({
	doctype,
	dirty: () => dirty.value,
	ready: () => controller.value?.ready.value ?? false,
	replaying: () => controller.value?.isReplaying.value ?? false,
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
			{ single, follow: follow.value }
		)
	);
	return items;
}

// A failure toasts here: `runAction` would otherwise reload over the draft. Clicks queue, so
// each one reads the state the one before it left and two quick clicks toggle twice.
function toggleOnSidecar(
	page: RecordPageApi,
	write: () => Promise<Envelope<Partial<DocInfo>>>,
	after?: (answer: Envelope<Partial<DocInfo>>) => void
) {
	return currentVisit.inTurn(async () => {
		// A turn that outlived its record would read the next record's state; it does nothing.
		if (page.doctype !== doctype.value || page.docname !== docname.value) return;
		const visit = currentVisit;
		try {
			const answer = await write();
			if (!visit.current()) return;
			docinfo.value = mergePart(docinfo.value, answer.data);
			after?.(answer);
		} catch (e) {
			toast.error(errorMessage(e));
		}
	});
}

function toggleFavourite(page: RecordPageApi) {
	return toggleOnSidecar(page, () =>
		(favourited.value ? removeFavourite : addFavourite)(page.doctype, page.docname)
	);
}

// The server declines a follow without failing, and says why beside the data.
function toggleFollow(page: RecordPageApi) {
	let adding = false;
	return toggleOnSidecar(
		page,
		() => {
			adding = !following.value;
			return (adding ? addFollow : removeFollow)(page.doctype, page.docname);
		},
		(answer) => {
			const message = declinedMessage(answer, adding);
			if (message) toast.error(message);
		}
	);
}

function visitCheck() {
	return currentVisit.current;
}

// Three built-ins first, then the Side Panel layout's sections, as they resolve now.
function panelBuiltins() {
	return [...PANEL_BUILTINS, ...layoutItems(sections.value)];
}

function chooseFormTab(identity: string) {
	formTab.value = identity;
	tabMemory.value.remember(identity);
}

// Several picks in one gesture each fire one re-read.
function reloadDocinfo(): Promise<void> {
	const shown = doctype.value;
	if (!shown) return Promise.resolve();
	return currentVisit.readNewest(
		(signal) => loadParts(shown, docname.value, signal),
		(fresh) => void (docinfo.value = fresh)
	);
}

// Only the route's load may paint from memory: a reload, a conflict or a failed action reads the server.
async function load({ fromMemory = false } = {}) {
	feeds.endKeptRead();
	releaseFresh();
	if (!doctype.value) {
		live.release();
		return;
	}
	currentVisit = currentVisit.next();
	const target = { doctype: doctype.value, name: docname.value };
	const pointed = feeds.pointerOnOpen(target.doctype, target.name, route.query);
	// Read before this load writes a view of its own.
	const view = fromMemory ? recallView(target.doctype, target.name, isNewNavigation()) : null;
	const pointer = view ? "" : pointed;
	openedQuery.value = view ? { ...route.query, tab: view.tab } : route.query;
	keeper = viewKeeper(target.doctype, target.name);
	keeping = false;
	error.value = "";
	live.follow(target.doctype, target.name);

	// Blanked before the fetch: the heading changes synchronously, and the old controller's quick
	// actions close over the previous page. `saved` goes with `doc` so `isDirty` stays false.
	blank();
	formTab.value = view?.formTab ?? tabMemory.value.recall();
	formSections.value = view?.sections ?? {};
	activeFormTab.value = "";

	// Scripts and layouts need only the doctype, so they ride beside the record read and meta.
	void loadClientScripts(target.doctype);
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
	const opening = { visit: currentVisit, target, pointer, details, panel, view };
	const fromCache = fromMemory ? openFromMemory(opening) : null;
	if (fromCache) return fromCache;
	await withFeedRead(target.doctype, target.name, openedQuery.value, (feedRead) =>
		openRecord({ ...opening, feedRead })
	);
}

function blank() {
	doc.value = {};
	saved.value = {};
	docinfo.value = null;
	linkTitles.value = {};
	controller.value?.leave();
	controller.value = null;
	panelLayout.value = null;
	detailsLayout.value = null;
	disclosure.reset();
}

interface Opening {
	visit: Visit;
	target: { doctype: string; name: string };
	pointer: string;
	details: UseFormLayout;
	panel: UseFormLayout;
	/** The reader's view to put back on a return, or null on a new visit. */
	view: RecordView | null;
}

interface OpenRecord extends Opening {
	feedRead: Promise<void>;
}

type BackgroundRead = Promise<() => Promise<void> | void>;

/** A return visit: paints before the first await, then re-reads quietly and replays once; null when memory lacks anything. */
function openFromMemory(opening: Opening): Promise<void> | null {
	const { visit, target, pointer, details, panel } = opening;
	const record = readCachedRecord(target.doctype, target.name);
	if (!record) return null;
	const metadata = metaInMemory(target.doctype);
	const layouts = !details.loading.value && !panel.loading.value;
	if (!metadata || !layouts || !feedInMemory(target.doctype, target.name, openedQuery.value))
		return null;
	show(record, metadata);
	const created = buildController(opening);
	if (!created.paintNow()) {
		blank();
		return null;
	}
	const release = holdFresh();
	releaseFresh = release;
	const reads = backgroundReads(opening, created);
	landPaint(created, pointer);
	void settleView(visit, opening.view);
	return applyInBackground(visit, created, reads, release);
}

// Each read resolves to its applier, which may return a re-read to wait for; they all apply in one step.
function backgroundReads(opening: Opening, created: RecordPageController): BackgroundRead[] {
	const { target, visit } = opening;
	const before = docinfo.value;
	const reads: BackgroundRead[] = [
		loadRecord(target.doctype, target.name, visit.signal).then(
			(fresh) => () => takeRefetch(fresh, before),
			(failure) => () => takeReadFailure(failure)
		),
		freshVersion(opening),
	];
	const rows = feeds.rereadKept(openedQuery.value);
	if (rows) reads.push(rows);
	// Called after `paintNow`, which reads the keys to fetch. Only a replay reads the values,
	// so they need no applier.
	reads.push(created.fetchCached().then(() => () => {}));
	return reads;
}

/** A stale meta, layout or script tier: resolves once the fresh ones are in, to the step that shows the meta. */
function freshVersion({ target, details, panel }: Opening): BackgroundRead {
	// The entry the layouts joined against, so a later DocType change cannot hand the page another.
	const held = useDoctypeMeta(target.doctype);
	// A script whose module hangs must not hold back the record's re-read; the replay still waits for it.
	const tier = Promise.race([
		loadClientScripts(target.doctype).catch(() => {}),
		new Promise((resolve) => setTimeout(resolve, LATE_LIMIT_MS)),
	]);
	return Promise.all([details.refreshed(), panel.refreshed(), tier]).then(() => () => {
		const fresh = held.meta.value;
		if (fresh && fresh !== meta.value) meta.value = fresh;
	});
}

/** Every read applied together and any docinfo re-read landed, then one replay whose acts are dropped. */
async function applyInBackground(
	visit: Visit,
	created: RecordPageController,
	reads: BackgroundRead[],
	release: () => void
) {
	try {
		const settled = await Promise.allSettled(reads);
		if (!visit.current()) return;
		// Fresh meta and layouts land with the appliers, so the page changes in one step.
		release();
		const rereads = settled.map((read) =>
			read.status === "fulfilled" ? read.value() : undefined
		);
		await Promise.all(rereads);
		if (!visit.current() || error.value) return;
	} finally {
		release();
		if (visit.current()) feeds.endKeptRead();
	}
	await created.refresh({ background: true });
}

// Written to the refs, never through the commit channel, so no field handler fires.
function takeRefetch(fresh: LoadedRecord, before: DocInfo | null) {
	const merged = mergeRefetch({ doc: doc.value, saved: saved.value }, fresh.document);
	saved.value = merged.saved;
	doc.value = merged.doc;
	if (!same(linkTitles.value, fresh.linkTitles)) linkTitles.value = fresh.linkTitles;
	// A write or live update since the reads began may be missing from `fresh`; a new read includes it.
	if (docinfo.value !== before) return reloadDocinfo().catch(warnDocinfoFailed);
	if (!same(before, fresh.docinfo)) docinfo.value = fresh.docinfo;
}

// A denied or deleted record leaves the page as a cold load's answer would; any other failure keeps it.
function takeReadFailure(failure: unknown) {
	if (!isApiError(failure) || (failure.status !== 403 && failure.status !== 404)) return;
	blank();
	error.value = readFailure(failure);
}

function readFailure(failure: unknown) {
	return isApiError(failure) && failure.status === 403
		? __("You do not have permission to read this record.")
		: __("Not found.");
}

function show(loaded: LoadedRecord, metadata: any) {
	saved.value = { ...loaded.document };
	doc.value = JSON.parse(JSON.stringify(loaded.document));
	docinfo.value = loaded.docinfo;
	linkTitles.value = loaded.linkTitles;
	meta.value = metadata;
}

function landPaint(created: RecordPageController, pointer: string) {
	actionsVersion.value++;
	if (pointer) created.page.activity.scrollTo(pointer);
}

/** The record read, then the page's first paint; a newer load cuts it short at any wait. */
async function openRecord({ visit, target, pointer, details, panel, view, feedRead }: OpenRecord) {
	try {
		const [loaded, metadata] = await Promise.all([
			loadRecord(target.doctype, target.name, visit.signal),
			fetchMeta(target.doctype),
		]);
		if (!visit.current()) return;
		show(loaded, metadata);
	} catch (e) {
		if (!visit.current()) return;
		error.value = readFailure(e);
		return;
	}

	const created = buildController({ visit, target, pointer, details, panel, view });
	// The first replay must see both layouts, or a script's act on a tab or section is dropped as unknown,
	// and the Activity rows when their read began beside the record's.
	await Promise.all([details.settled(), panel.settled(), feedRead]);
	if (!visit.current()) return;
	await created.refresh();
	if (!visit.current()) return;
	landPaint(created, pointer);
	// The shown tab's body has mounted once this lands; a feed body that mounts later reads what it missed.
	await settleView(visit, view);
}

/** Puts the view back over the first paint's acts, before the frame when the body is drawn; the page keeps its view from then on. */
async function settleView(visit: Visit, view: RecordView | null) {
	if (view) {
		disclosure.restore(view.panel);
		tabsHost.settleRestored(view.tab);
	}
	await nextTick();
	const root = bodyRoot.value;
	if (!visit.current()) return;
	if (view && root) {
		// A tab that is gone takes the new visit's tab, which starts at the top.
		const offsets =
			shownTab.value === view.tab ? view.offsets : { columns: view.offsets.columns };
		await landOffsets(root, shownTab.value, offsets);
		if (!visit.current()) return;
	}
	keeping = true;
	keep();
}

function keep() {
	const root = bodyRoot.value;
	if (!keeper || !keeping || !root || !painted.value) return;
	// A route that moved on to the next record resets the tab before its load starts.
	const { page } = painted.value;
	if (page.doctype !== doctype.value || page.docname !== docname.value) return;
	keeper({
		tab: shownTab.value,
		formTab: activeFormTab.value || formTab.value,
		// A copy: `history.replaceState` cannot clone a reactive proxy.
		sections: { ...formSections.value },
		panel: disclosure.shown(),
		offsets: readOffsets(root, shownTab.value),
	});
}

/** A link that names a tab or an activity row opens the record as asked, not as it was left. */
function isNewNavigation() {
	return route.query.tab !== undefined || activityPointer(route.query) !== "";
}

/** The page's controller with its built-ins, made current. */
function buildController({ target, pointer, details, panel, view }: Opening) {
	const created = createRecordPage({
		doctype: target.doctype,
		docname: target.name,
		doc,
		saved,
		meta,
		perms: () => docinfo.value?.permissions ?? {},
		isDirty: () => dirty.value,
		...tabsPageHost,
		...feeds.pageHost,
		...composerHost(target.doctype, target.name, {
			page: () => controller.value?.page,
			userEmail: boot.session.user.email,
		}),
		formLayout: () => detailsForm.value,
		activateFormTab: (identity) => void (formTab.value = identity),
		discloseSection: disclosure.disclose,
		focusField: (fieldname, cursor) => void focusOnDetails(fieldname, cursor),
		save: write,
		reload: load,
		router,
		sourcesReady: () => loadClientScripts(target.doctype),
		restoresView: () => view !== null,
	});
	created.header.provideBuiltins(headerBuiltins);
	created.quickActions.provideBuiltins(() =>
		quickActionBuiltins(
			docinfo.value?.permissions ?? {},
			tagsOf(docinfo.value).length > 0,
			follow.value,
			stripTabs.value.find((tab) => tab.name === FILES_TAB)?.create
		)
	);
	created.tabs.provideBuiltins(() =>
		recordTabBuiltins({
			requestUpload: docinfo.value?.permissions?.write
				? () => feeds.requestUpload()
				: undefined,
		})
	);
	created.composer.provideBuiltins(() => composerBuiltins(docinfo.value?.permissions ?? {}));
	created.panelSections.provideBuiltins(panelBuiltins);
	created.form.provideBuiltins(() => formItems(detailsForm.value));
	panelLayout.value = panel;
	detailsLayout.value = details;
	controller.value = created;
	feeds.showPointedTab(pointer);
	// After `controller` is set, whose change resets the strip to the address's tab.
	if (view) tabsHost.restore(view.tab);
	return created;
}

async function write() {
	// Refuse to write the wrong record if the route moved while an action ran.
	if (doc.value.name !== docname.value || doctype.value === null) {
		throw new Error("The record changed while saving; nothing was written.");
	}
	const visit = currentVisit;
	const document = await saveRecord(doctype.value!, doc.value).catch(rethrowSaveError);
	if (!visit.current()) return;
	saved.value = { ...document };
	doc.value = JSON.parse(JSON.stringify(document));
	// A save writes a version row and its hooks may assign.
	live.reloadQuietly();
	await controller.value?.refresh();
	actionsVersion.value++;
}

// A conflict is resolved with the reader; any other refusal reads as text, since a msgprint is often HTML.
async function rethrowSaveError(e: unknown): Promise<never> {
	if (isApiError(e) && e.isTimestampMismatch) {
		await resolveConflict();
		throw conflictError();
	}
	throw isApiError(e) ? new Error(stripTags(e.message)) : e;
}

// Nothing is re-applied: the reader sees who saved and what they changed, and chooses.
async function resolveConflict() {
	const visit = currentVisit;
	const latest = await loadRecord(doctype.value!, docname.value, visit.signal).catch(() => null);
	if (!visit.current()) return;
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
	const current = controller.value!;
	try {
		await current.hold(() => action.run?.(current.page));
	} catch (e) {
		const name = (e as Error)?.name;
		if (name === SAVE_CONFLICT) return;
		toast.error(errorMessage(e));
		if (name !== SAVE_VETO) await load();
	}
}

async function focusOnDetails(fieldname: string, cursor: boolean) {
	if (await tabsHost.showDetails(fieldname)) await landOn(fieldname, cursor);
}

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

// A push still holds the entry being left, so its history entry takes the view as it is now.
onBeforeRouteLeave(() => {
	keep();
	return confirmLeave();
});
onBeforeRouteUpdate((to, from) => {
	if (to.params.doctype === from.params.doctype && to.params.name === from.params.name)
		return true;
	keep();
	return confirmLeave();
});

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
	currentVisit.end();
	controller.value?.leave();
	live.dispose();
	feeds.endKeptRead();
	releaseFresh();
	window.removeEventListener("keydown", onKeydown);
	window.removeEventListener("beforeunload", onBeforeUnload);
});

watch(
	() => [shownTab.value, activeFormTab.value, formSections.value, disclosure.shown()],
	() => keep()
);
watch(bodyRoot, (root, _previous, onCleanup) => {
	if (root) onCleanup(onScrollSettled(root, keep));
});
watch([doctype, docname], () => load({ fromMemory: true }), { immediate: true });
// The page's own `?tab=` replace keeps the key, so only a new pointer on the same record moves the reader.
watch(
	() => activityPointer(route.query),
	() => feeds.followPointer(doctype.value ?? "", docname.value, route.query)
);
</script>
