import { computed, shallowReactive, toValue, watch } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import type { DialogSize } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import type { FormLayoutSchema, RawMetaField, TabOverride } from "@framework/ui/FormLayout/types";
import type { Decorator } from "@framework/ui/FormLayout";
import type { FieldPatch } from "./fieldPatch";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { useDocPermissions, type FieldAccess } from "@framework/ui/useDocPermissions";
import { landFresh, memoizedState } from "@framework/ui/utils";
import { chooseRow } from "./chooseLayout";
import { accessAtDocstatus, withAccess } from "./fieldAccess";
import { joinLayout } from "./joinLayout";
import type { FormLayoutRow, FormLayoutsResponse, FormLayoutType } from "./types";
import { placedFieldnames, requiredOffLayout, type UnplacedRule } from "./unplaced";

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
	/** Fieldnames another layout on the page places, so an anchor does not draw them twice. */
	placedElsewhere?: MaybeRefOrGetter<string[]>;
	/** A saved record: the `field:` autoname field reads only; the server resets an edit to the name. */
	lockAutoname?: boolean;
}

export interface UseFormLayout {
	/** Render-ready schema; empty until the rows and the meta both load. */
	layout: ComputedRef<FormLayoutSchema>;
	/** Details and New Record: the mandatory fields the row does not show, which a save asks for. */
	offLayout: ComputedRef<FormLayoutSchema>;
	/** True while nothing is there to show; stale rows or meta show while fresh ones are read. */
	loading: ComputedRef<boolean>;
	error: ComputedRef<unknown>;
	/** `Quick Entry` only: the server's answer to whether Create opens a dialog. */
	dialog: ComputedRef<boolean>;
	/** `Quick Entry` only: the size the row in use gives the dialog; `null` when it gives none. */
	dialogSize: ComputedRef<DialogSize | null>;
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
	const permissions = useDocPermissions(options.doctype);
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

		return joinLayout(tree, fields, {
			...joinOptions(),
			tabOverrides: toValue(options.tabOverrides),
			unplaced: row.value
				? unplacedRule(options.type, row.value, toValue(options.placedElsewhere))
				: undefined,
		});
	});

	// Only a row leaves fields out: the fallback draws them all, and Quick Entry adds its own.
	const offLayout = computed<FormLayoutSchema>(() => {
		const fields = meta.value?.fields;
		if (!row.value || !fields || options.type === "Side Panel" || options.type === "Quick Entry")
			return [];
		const shown = [...layoutFieldnames(layout.value), ...(toValue(options.placedElsewhere) ?? [])];
		const required = requiredOffLayout(shown, fields, fieldAccess());
		if (!required.length) return [];
		const column = { name: "column_1", fields: required.map((field) => field.fieldname) };
		const tree = [{ name: "required", sections: [{ name: "required", columns: [column] }] }];
		return joinLayout(tree, fields, joinOptions());
	});

	// A saved record's docstatus locks its fields; a New Record's opening values never do.
	function docstatus(): number | undefined {
		const saved = options.type === "Details" || options.type === "Side Panel";
		return saved ? options.doc?.value?.docstatus : undefined;
	}

	function fieldAccess() {
		const base = options.lockAutoname
			? lockingAutoname(permissions.fieldAccess, autonameField(meta.value?.autoname))
			: permissions.fieldAccess;
		return lockingSubmitted(base, docstatus());
	}

	function joinOptions() {
		const locked = docstatus();
		const childMetas: Record<string, RawMetaField[]> = {};
		for (const [name, m] of Object.entries(metas.value))
			if (m.fields)
				childMetas[name] = locked
					? m.fields.map((field) =>
							withAccess(field, (one) => accessAtDocstatus("write", one, locked))
					  )
					: m.fields;
		return {
			childMetas,
			childLayouts: response.value?.children,
			fieldAccess: fieldAccess(),
			decorate: options.decorate,
			overrides: toValue(options.overrides),
		};
	}

	const busy = computed(() => loading.value || entry.value.loading);
	const stale = computed(() => busy.value || refreshing.value || entry.value.refreshing);

	return {
		layout,
		offLayout,
		loading: busy,
		error: computed(() => error.value ?? entry.value.error),
		dialog: computed(() => Boolean(response.value?.dialog)),
		dialogSize: computed(() => row.value?.size ?? null),
		placed: computed(() => placedFieldnames(row.value?.layout ?? null)),
		reload: () => entry.value.reload(),
		settled: () => whenSettled(stale),
		refreshed: () => Promise.all([refreshed(), entry.value.refreshed]).then(() => {}),
	};
}

/** The field `Document._sync_autoname_field` resets on save, so only the literal `field:` rule. */
function autonameField(autoname: string | undefined): string | null {
	return autoname?.startsWith("field:") ? autoname.slice("field:".length) || null : null;
}

function lockingSubmitted(
	fieldAccess: (field: RawMetaField) => FieldAccess,
	docstatus: number | undefined
): (field: RawMetaField) => FieldAccess {
	return (field) => accessAtDocstatus(fieldAccess(field), field, docstatus);
}

function lockingAutoname(
	fieldAccess: (field: RawMetaField) => FieldAccess,
	locked: string | null
): (field: RawMetaField) => FieldAccess {
	return (field) => {
		const access = fieldAccess(field);
		return access === "write" && field.fieldname === locked ? "read" : access;
	};
}

/** With no row, the fallback already draws every field, so only a row gets a rule. */
function unplacedRule(
	type: FormLayoutType,
	row: FormLayoutRow,
	placedElsewhere?: string[]
): UnplacedRule | undefined {
	if (type === "Quick Entry") return { mandatoryAtEnd: true };
	if (type === "Side Panel") return undefined;
	return { anchors: true, omitted: row.omitted, placedElsewhere };
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

/** Marks the doctype's rows of every type stale, every parent's that carries them as a child's, and every first read in flight. */
export function markFormLayoutsStale(doctype: string): void {
	entries.stale(
		(key, entry) =>
			key.startsWith(`${doctype}:`) ||
			entry.loading ||
			Boolean(entry.data?.children?.[doctype])
	);
}

/** The shell's app: its `Form Layout` rows replace the rows naming no app. `null` on the `/apps` index. */
export function setFormLayoutApp(app: string | null): void {
	layoutApp = app;
}

/** Drops every memoised fetch, so one test's rows cannot reach the next. */
export function resetFormLayouts(): void {
	entries.reset();
}

const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";

let layoutApp: string | null = null;

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
				{ dt: input.doctype, type: input.type, ...(layoutApp && { app: layoutApp }) },
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

function layoutFieldnames(layout: FormLayoutSchema): string[] {
	return layout.flatMap((tab) =>
		tab.sections.flatMap((section) => section.columns.flatMap((column) => column.fields.map((field) => field.fieldname)))
	);
}
