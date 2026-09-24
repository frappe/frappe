import { computed, shallowReactive, toValue, watch } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { runMethod } from "@framework/ui/api";
import type {
	FormLayoutSchema,
	RawMetaField,
	TabOverride,
} from "@framework/ui/components/FormLayout/types";
import type { Decorator } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import type { FieldPatch } from "./fieldPatch";
import { useDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { useDocPermissions } from "@framework/ui/composables/useDocPermissions";
import { memoizedState } from "@framework/ui/utils/sharedState";
import { chooseLayout } from "./chooseLayout";
import { joinLayout } from "./joinLayout";
import type { FormLayoutsResponse, FormLayoutType } from "./types";

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
}

export interface UseFormLayout {
	/** Render-ready schema; empty until the rows and the meta both load. */
	layout: ComputedRef<FormLayoutSchema>;
	loading: ComputedRef<boolean>;
	error: ComputedRef<unknown>;
	/** Re-fetch the layout rows (the meta reloads through `useDoctypeMeta`). */
	reload: () => void;
	/** Resolves once the rows and the meta have both landed or failed, so a first replay sees the layout. */
	settled: () => Promise<void>;
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
	const { meta, metas, loading, error } = useDoctypeMeta(options.doctype);
	const { fieldAccess } = useDocPermissions(options.doctype);
	const entry = computed(() =>
		entries.get({ doctype: toValue(options.doctype), type: options.type })
	);
	// Read at call time: that fetches now, and the handle keeps this entry until the doctype moves.
	void entry.value;

	const layout = computed<FormLayoutSchema>(() => {
		const response = entry.value.data as FormLayoutsResponse | null;
		const fields = meta.value?.fields;
		if (!response || !fields) return [];

		const doc = options.doc?.value ?? {};
		const chosen = chooseLayout(response.layouts, doc);
		const tree =
			chosen ?? (options.fallback === "none" ? null : response.fallback);
		if (!tree) return [];

		const childMetas: Record<string, RawMetaField[]> = {};
		for (const [name, m] of Object.entries(metas.value))
			if (m.fields) childMetas[name] = m.fields;

		return joinLayout(tree, fields, {
			childMetas,
			fieldAccess,
			decorate: options.decorate,
			overrides: toValue(options.overrides),
			tabOverrides: toValue(options.tabOverrides),
		});
	});

	const busy = computed(() => loading.value || entry.value.loading);

	return {
		layout,
		loading: busy,
		error: computed(() => error.value ?? entry.value.error),
		reload: () => entry.value.reload(),
		settled: () => whenSettled(busy),
	};
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

/** Forgets the doctype's rows of every type; the next caller fetches. */
export function dropFormLayouts(doctype: string): void {
	entries.drop((key) => key.startsWith(`${doctype}:`));
}

/** Drops every memoised fetch, so one test's rows cannot reach the next. */
export function resetFormLayouts(): void {
	entries.reset();
}

const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";

function buildEntry(input: { doctype: string; type: FormLayoutType }) {
	const entry = shallowReactive({
		data: null as FormLayoutsResponse | null,
		loading: false,
		error: null as unknown,
		reload,
	});
	// The slower of two reloads must not overwrite the newer answer.
	let turn = 0;

	async function reload() {
		const mine = ++turn;
		entry.loading = true;
		try {
			const { data } = await runMethod<FormLayoutsResponse>(
				GET_FORM_LAYOUTS,
				{ dt: input.doctype, type: input.type },
				{ http: "GET" }
			);
			if (mine !== turn) return;
			entry.data = data;
			entry.error = null;
		} catch (caught) {
			if (mine !== turn) return;
			entry.error = caught;
		} finally {
			if (mine === turn) entry.loading = false;
		}
	}

	reload();
	return entry;
}
