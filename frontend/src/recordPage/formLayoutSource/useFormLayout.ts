import { computed, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { createResource, frappeRequest } from "frappe-ui";
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
			tabOverrides: toValue(options.tabOverrides),
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
