import { computed, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { createResource, frappeRequest } from "frappe-ui";
import type {
	FieldOverride,
	FormLayoutSchema,
	RawMetaField,
} from "../../components/FormLayout/types";
import type { Decorator } from "../../components/FormLayout/buildLayoutFromMeta";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { useDocPermissions } from "../../composables/useDocPermissions";
import { memoizedState } from "../../utils/sharedState";
import { chooseLayout } from "./chooseLayout";
import { joinLayout } from "./joinLayout";
import type { FormLayoutsResponse, FormLayoutType } from "./types";

export interface UseFormLayoutOptions {
	doctype: MaybeRefOrGetter<string>;
	type: FormLayoutType;
	/** The doc conditions evaluate against. Reactive — the layout re-picks when
	 *  it changes — so pass the saved snapshot, not the draft, unless a mid-edit
	 *  remount (and the focus loss it brings) is acceptable. */
	doc?: Ref<Record<string, any>>;
	/** What renders when no row applies: the meta-derived layout (default), or
	 *  nothing — `"none"` lets the caller chain its own fallback (the side
	 *  panel falls through to the Details layout). */
	fallback?: "meta" | "none";
	/** Per-field UI overlay hook; what makes a `Button` field clickable. */
	decorate?: Decorator;
	/**
	 * Per-render field property overrides, keyed by fieldname. Plain data:
	 * nothing here knows who wrote the override.
	 *
	 * Reactive — pass a getter and the layout re-joins when the app changes its
	 * mind — but note *re-joins*: changing one boolean re-runs the whole meta
	 * join, re-invokes `decorate` for every field and rebuilds every child
	 * table's columns and row layout. Cheap for a handful of fields on a load;
	 * if a caller ever flips these per keystroke, attach them in a shallow pass
	 * over an already-joined tree instead.
	 */
	overrides?: MaybeRefOrGetter<Record<string, FieldOverride>>;
}

export interface UseFormLayout {
	/** Render-ready schema; empty until the rows and the meta both load. */
	layout: ComputedRef<FormLayoutSchema>;
	loading: ComputedRef<boolean>;
	error: ComputedRef<unknown>;
	/** Re-fetch the layout rows (the meta reloads through `useDoctypeMeta`). */
	reload: () => void;
}

/** One fetch per `(doctype, type)`, shared by every caller. */
const entries = memoizedState(
	(input: { doctype: string; type: FormLayoutType }) =>
		`${input.doctype}:${input.type}`,
	buildEntry
);

/**
 * The generic record-form layout source: fetch the doctype's `Form Layout`
 * rows, pick the row whose condition matches the doc (re-evaluated as the doc
 * changes, so the layout switches live), fall back to the meta-derived layout,
 * and join fieldnames against the doctype meta — permlevel baked in via
 * `useDocPermissions`.
 */
export function useFormLayout(options: UseFormLayoutOptions): UseFormLayout {
	const { meta, metas, loading, error } = useDoctypeMeta(options.doctype);
	const { fieldAccess } = useDocPermissions(options.doctype);
	// Warm the current entry at call time; the computed tracks it from there.
	const current = () =>
		entries.get({ doctype: toValue(options.doctype), type: options.type });
	current();
	const entry = computed(current);

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
		});
	});

	return {
		layout,
		loading: computed(() => loading.value || entry.value.loading),
		error: computed(() => error.value ?? entry.value.error),
		reload: () => entry.value.reload(),
	};
}

/** Drops every memoised fetch, so one test's rows cannot reach the next. */
export function resetFormLayouts(): void {
	entries.reset();
}

function buildEntry(input: { doctype: string; type: FormLayoutType }) {
	const resource = createResource({
		url: "frappe.desk.doctype.form_layout.form_layout.get_form_layouts",
		params: { dt: input.doctype, type: input.type },
		cache: ["Form Layout", input.doctype, input.type],
		resourceFetcher: frappeRequest,
	});
	if (!resource.fetched && !resource.loading) resource.fetch();
	return resource;
}
