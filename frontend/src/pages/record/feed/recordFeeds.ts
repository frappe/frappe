// The record page's feeds, host side: what `page.activity` and `page.files` read, and what the tab bodies share.
import { nextTick, shallowRef, type InjectionKey, type Ref } from "vue";
import type { LocationQuery } from "vue-router";
import { until } from "@vueuse/core";
import {
	activityTimelineRows,
	endActivityPrefetch,
	prefetchActivityTimeline,
	reloadActivityTimeline,
	type VisibleTypes,
} from "@framework/ui/ActivityTimeline";
import { removeAttachment, type AttachmentsPart } from "@framework/ui/api";
import type { ActivityRow, FileRow, RecordPageController } from "@/recordPage";
import type { DocInfo } from "../panel/context";
import { mergePart } from "../panel/peopleActions";
import { attachTransport, byTime } from "./files";

export const ACTIVITY_TAB = "activity";
export const EMAILS_TAB = "emails";
export const EMAIL_TYPES: VisibleTypes = ["email"];

// A body replaced by a script's component never registers, so the wait gives up.
const DRAW_TIMEOUT_MS = 2000;

/** The store's `paginate`, read without `.value`. */
export interface FeedPages {
	hasNextPage: boolean;
	isFetchingNextPage: boolean;
	fetchNextPage: () => Promise<void> | void;
}

/** What the Activity tab's body hands the host while it is mounted. */
export interface ActivityTimelineHandle {
	activities: Readonly<Ref<ActivityRow[]>>;
	loading: Readonly<Ref<boolean>>;
	error: Readonly<Ref<unknown>>;
	paginate: FeedPages;
	reload: () => Promise<void>;
	scrollToRow: (key: string) => boolean;
}

export interface RecordFeedsOptions {
	docinfo: Ref<DocInfo | null>;
	controller: () => RecordPageController | null;
	/** Brings a tab forward; false, with a warning naming `what`, when a script hid it. */
	showTab: (name: string, what: string) => Promise<boolean>;
	reloadParts: () => Promise<void>;
	whileOnRecord: () => () => boolean;
}

export const RecordFeedsKey: InjectionKey<RecordFeeds> = Symbol("record-feeds");

export class RecordFeeds {
	private readonly timeline = shallowRef<ActivityTimelineHandle | null>(null);
	private opened = "";

	constructor(private readonly options: RecordFeedsOptions) {}

	/** The host members `createRecordPage` takes. */
	readonly pageHost = {
		activityRows: (): ActivityRow[] => this.timeline.value?.activities.value ?? this.storedRows(),
		scrollToActivity: (key: string) => this.scrollToActivity(key),
		reloadActivity: () => this.timeline.value?.reload() ?? this.rereadStore(),
		fileRows: () => this.fileRows(),
		reloadFiles: () => this.options.reloadParts(),
	};

	/** Opens Activity, then pages older until the row is drawn; false if the list ended first, null if the tab is hidden or drew no feed. */
	async scrollToActivity(key: string): Promise<boolean | null> {
		const current = this.options.whileOnRecord();
		const what = `page.activity.scrollTo("${key}") — the Activity tab`;
		if (!(await this.options.showTab(ACTIVITY_TAB, what))) return null;
		const timeline = await until(this.timeline).toBeTruthy({ timeout: DRAW_TIMEOUT_MS });
		if (timeline) return pageUntilDrawn(timeline, key, current);
		warn(`${what} drew no activity feed, so the reader was not moved.`);
		return null;
	}

	/** `?activity=<key>` as a record opens; a reload of the same record reads none. */
	pointerOnOpen(doctype: string, docname: string, query: LocationQuery): string {
		const record = JSON.stringify([doctype, docname]);
		const opening = record !== this.opened;
		this.opened = record;
		return opening ? activityPointer(query) : "";
	}

	/** A pointer names its own tab, so Activity comes forward over any `?tab=` before the strip paints. */
	showPointedTab(pointer: string) {
		if (pointer) void this.options.showTab(ACTIVITY_TAB, `?activity=${pointer} — the Activity tab`);
	}

	/** The Activity body registers while mounted; the returned function lets go. */
	attach(timeline: ActivityTimelineHandle) {
		this.timeline.value = timeline;
		return () => {
			if (this.timeline.value === timeline) this.timeline.value = null;
		};
	}

	controller() {
		return this.options.controller();
	}

	docinfo() {
		return this.options.docinfo.value;
	}

	/** The record read's `attachments` part, oldest first. */
	fileRows(): FileRow[] {
		const rows = this.options.docinfo.value?.attachments ?? [];
		return [...rows].sort(byTime);
	}

	/** Uploads onto the record; each answer replaces the part, unless the page has moved on. */
	uploadTransport(doctype: string, docname: string) {
		const current = this.options.whileOnRecord();
		return attachTransport({ doctype, docname }, (part) => this.keepFiles(part, current));
	}

	async removeFile(doctype: string, docname: string, file: string) {
		const current = this.options.whileOnRecord();
		const { data } = await removeAttachment(doctype, docname, file);
		this.keepFiles(data, current);
	}

	// Before the Activity body mounts, the store a prefetch filled answers for it.
	private storedRows(): ActivityRow[] {
		const read = this.activityRead();
		return read ? (activityTimelineRows(...read) as ActivityRow[]) : [];
	}

	private rereadStore(): Promise<void> {
		const read = this.activityRead();
		return read ? reloadActivityTimeline(...read) : Promise.resolve();
	}

	/** The read the Activity body makes: this record, in the types a script chose. */
	private activityRead() {
		const controller = this.options.controller();
		if (!controller) return null;
		const { doctype, docname } = controller.page;
		return [doctype, docname, controller.activity.shownTypes() ?? undefined] as const;
	}

	private keepFiles({ attachments, users }: AttachmentsPart, current: () => boolean) {
		if (!current()) return;
		this.options.docinfo.value = mergePart(this.options.docinfo.value, { attachments, users });
	}
}

/** Runs a record's open with the feed read started beside it; the first-paint pass ends however the open ends. */
export async function withFeedRead(
	doctype: string,
	docname: string,
	query: LocationQuery,
	open: (feedRead: Promise<void>) => Promise<void>
) {
	const feedRead = prefetchFeed(doctype, docname, query);
	try {
		await open(feedRead);
	} finally {
		endPrefetchFeed(doctype, docname);
	}
}

/** Starts the feed read beside the record read when the address opens a feed tab; resolves once the Activity page is in. */
export function prefetchFeed(doctype: string, docname: string, query: LocationQuery): Promise<void> {
	const tab = addressedTab(query);
	if (tab === EMAILS_TAB) void prefetchActivityTimeline(doctype, docname, EMAIL_TYPES);
	return tab === ACTIVITY_TAB ? prefetchActivityTimeline(doctype, docname) : Promise.resolve();
}

/** After the first paint: a feed body that mounts later catches up on what the eager read missed. */
export function endPrefetchFeed(doctype: string, docname: string) {
	endActivityPrefetch(doctype, docname);
	endActivityPrefetch(doctype, docname, EMAIL_TYPES);
}

/** `?activity=<key>`, or `""`. */
export function activityPointer(query: LocationQuery): string {
	const key = query.activity;
	return typeof key === "string" ? key : "";
}

// A pointer names its own tab, and an address with no `?tab=` opens the first one, Activity.
function addressedTab(query: LocationQuery) {
	if (activityPointer(query)) return ACTIVITY_TAB;
	return typeof query.tab === "string" && query.tab ? query.tab : ACTIVITY_TAB;
}

async function pageUntilDrawn(timeline: ActivityTimelineHandle, key: string, current: () => boolean) {
	await until(timeline.loading).toBe(false);
	while (current()) {
		await nextTick();
		if (timeline.scrollToRow(key)) return true;
		if (!timeline.paginate.hasNextPage || isLoaded(timeline, key)) return false;
		if (!(await readOlderPage(timeline))) return false;
	}
	return false;
}

// The store keeps an older read's failure on `error` and leaves `hasNextPage` true.
async function readOlderPage(timeline: ActivityTimelineHandle) {
	const before = timeline.error.value;
	await timeline.paginate.fetchNextPage();
	return !timeline.error.value || timeline.error.value === before;
}

// Loaded and still not drawn: netted out of a run, so no older page will draw it.
function isLoaded(timeline: ActivityTimelineHandle, key: string) {
	return timeline.activities.value.some((row) => row.key === key);
}

function warn(message: string) {
	if (import.meta.env.DEV) console.warn(`[record-page] ${message}`);
}
