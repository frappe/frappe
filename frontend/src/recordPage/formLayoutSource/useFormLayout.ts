import { computed, shallowReactive, toValue, watch } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { runMethod } from "@framework/ui/api";
import type { FormLayoutSchema, RawMetaField, TabOverride } from "@framework/ui/FormLayout/types";
import type { Decorator } from "@framework/ui/FormLayout";
import type { FieldPatch } from "./fieldPatch";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import { landFresh, memoizedState } from "@framework/ui/utils";
import { chooseRow } from "./chooseLayout";
import { joinLayout } from "./joinLayout";
import type { FormLayoutRow, FormLayoutsResponse, FormLayoutType } from "./types";
import { placedFieldnames, type UnplacedRule } from "./unplaced";

export interface UseFormLayoutOptions {
	doctype: MaybeRefOrGetter<string>;
	type: FormLayoutType;
	/** The doc conditions evaluate against. Reactive: pass the saved snapshot, or a mid-edit remount loses focus. */
	doc?: Ref<Record<string, any>>;
	/** What renders when no row applies: the meta layout, or nothing. The Side Panel passes
	 *  `"none"`, so it never shows the Details layout's fields twice. */
	fallback?: "meta" | "none";
	/** Per-field UI overlay hook; what makes a `Button` field clickable. */
	decorate?: Decorator;
	/** Per-render field overrides by fieldname. Reactive, and a change re-runs the whole
	 *  join, so never flip them per keystroke. */
	overrides?: MaybeRefOrGetter<Record<string, FieldPatch>>;
	/** Per-render tab overrides by identity; reactive on `overrides`' terms. */
	tabOverrides?: MaybeRefOrGetter<Record<string, TabOverride>>;
	/** Fieldnames another layout on the page places, so "More fields" does not draw them twice. */
	placedElsewhere?: MaybeRefOrGetter<string[]>;
}

export interface UseFormLayout {
	/** Render-ready schema; empty until the rows and the meta both load. */
	layout: ComputedRef<FormLayoutSchema>;
	/** True while nothing is there to show; stale rows or meta show while fresh ones are read. */
	loading: ComputedRef<boolean>;
	error: ComputedRef<unknown>;
	/** `Quick Entry` only: the server's answer to whether Create opens a dialog. */
	dialog: ComputedRef<boolean>;
	/** Fieldnames the row in use places; empty when no row applies. */
	placed: ComputedRef<string[]>;
	/** Re-fetch the layout rows (the meta reloads through `useDoctypeMeta`). */
	reload: () => void;
	/** Resolves once the fresh rows and meta have both landed or failed, so a first replay sees the layout. */
	settled: () => Promise<void>;
	/** Resolves once the fresh reads of stale rows and meta have arrived, shown or held. */
	refreshed: () => Promise<void>;
}

/** One fetch per `(doctype, type)`, shared by every caller. */
const entries = memoizedState(
	(input: { doctype: string; type: FormLayoutType }) =>
		`${input.doctype}:${input.type}`,
	buildEntry
);

/**
 * The record-form layout source: the doctype's `Form Layout` rows, the row whose condition
 * matches the doc, joined against the meta with permlevel baked in.
 */
export function useFormLayout(options: UseFormLayoutOptions): UseFormLayout {
	const { meta, metas, loading, refreshing, error, refreshed } = useDoctypeMeta(options.doctype);
	const { fieldAccess } = useDocPermissions(options.doctype);
	// Built at call time and held until the input moves, so a later stale mark cannot swap it.
	const inputNow = () => ({ doctype: toValue(options.doctype), type: options.type });
	const first = inputNow();
	let held = { input: first, entry: entries.get(first) };
	const entry = computed(() => {
		const input = inputNow();
		if (input.doctype !== held.input.doctype || input.type !== held.input.type)
			held = { input, entry: entries.get(input) };
		return held.entry;
	});

	const response = computed(() => entry.value.data as FormLayoutsResponse | null);
	const row = computed(() =>
		response.value ? chooseRow(response.value.layouts, options.doc?.value ?? {}) : null
	);

	const layout = computed<FormLayoutSchema>(() => {
		const fields = meta.value?.fields;
		if (!response.value || !fields) return [];

		const tree =
			row.value?.layout ?? (options.fallback === "none" ? null : response.value.fallback);
		if (!tree) return [];

		const childMetas: Record<string, RawMetaField[]> = {};
		for (const [name, m] of Object.entries(metas.value))
			if (m.fields) childMetas[name] = m.fields;

		return joinLayout(tree, fields, {
			childMetas,
			childLayouts: response.value.children,
			fieldAccess,
			decorate: options.decorate,
			overrides: toValue(options.overrides),
			tabOverrides: toValue(options.tabOverrides),
			unplaced: row.value
				? unplacedRule(options.type, row.value, toValue(options.placedElsewhere))
				: undefined,
		});
	});

	const busy = computed(() => loading.value || entry.value.loading);
	const stale = computed(() => busy.value || refreshing.value || entry.value.refreshing);

	return {
		layout,
		loading: busy,
		error: computed(() => error.value ?? entry.value.error),
		dialog: computed(() => Boolean(response.value?.dialog)),
		placed: computed(() => placedFieldnames(row.value?.layout ?? null)),
		reload: () => entry.value.reload(),
		settled: () => whenSettled(stale),
		refreshed: () => Promise.all([refreshed(), entry.value.refreshed]).then(() => {}),
	};
}

/** With no row, the fallback already draws every field, so only a row gets a rule. */
function unplacedRule(
	type: FormLayoutType,
	row: FormLayoutRow,
	placedElsewhere?: string[]
): UnplacedRule | undefined {
	if (type === "Quick Entry") return { mode: "mandatory" };
	if (type === "Side Panel") return undefined;
	return { mode: "section", omitted: row.omitted, placedElsewhere };
}

/** Answers now when nothing is loading; the entry raises its flag synchronously at fetch, so this cannot miss it. */
export function whenSettled(loading: { value: boolean }): Promise<void> {
	if (!loading.value) return Promise.resolve();
	return new Promise((resolve) => {
		const stop = watch(loading, (busy) => {
			if (busy) return;
			stop();
			resolve();
		});
	});
}

/** Marks the doctype's rows of every type stale, and every parent's that carries them as a child's. */
export function markFormLayoutsStale(doctype: string): void {
	entries.stale(
		(key, entry) => key.startsWith(`${doctype}:`) || Boolean(entry.data?.children?.[doctype])
	);
}

/** Drops every memoised fetch, so one test's rows cannot reach the next. */
export function resetFormLayouts(): void {
	entries.reset();
}

const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";

interface LayoutEntry {
	data: FormLayoutsResponse | null;
	loading: boolean;
	refreshing: boolean;
	error: unknown;
	reload: () => Promise<void>;
	refreshed: Promise<void>;
}

function buildEntry(input: { doctype: string; type: FormLayoutType }, stale?: LayoutEntry) {
	const data = stale?.data ?? null;
	let arrive = () => {};
	const entry: LayoutEntry = shallowReactive({
		data,
		loading: false,
		refreshing: data !== null,
		error: null as unknown,
		reload,
		refreshed: data === null ? Promise.resolve() : new Promise<void>((resolve) => (arrive = resolve)),
	});
	// The slower of two reloads must not overwrite the newer answer.
	let turn = 0;

	async function reload() {
		const mine = ++turn;
		entry.loading = !entry.refreshing;
		try {
			const { data } = await runMethod<FormLayoutsResponse>(
				GET_FORM_LAYOUTS,
				{ dt: input.doctype, type: input.type },
				{ http: "GET" }
			);
			if (mine !== turn) return;
			show(() => {
				entry.data = data;
				entry.error = null;
			});
		} catch (caught) {
			if (mine !== turn) return;
			// A failed refresh keeps the stale rows on show, and the next caller reads again.
			if (entry.refreshing) {
				entry.refreshing = false;
				entries.stale((_key, one) => one === entry);
			} else entry.error = caught;
		} finally {
			if (mine === turn) {
				entry.loading = false;
				arrive();
			}
		}
	}

	function show(commit: () => void) {
		if (!entry.refreshing) return commit();
		landFresh(() => {
			commit();
			entry.refreshing = false;
		});
	}

	reload();
	return entry;
}
