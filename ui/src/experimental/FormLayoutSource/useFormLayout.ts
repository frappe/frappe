import { computed, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { createResource, frappeRequest } from "frappe-ui";
import type {
	FormLayoutSchema,
	RawMetaField,
} from "../../components/FormLayout/types";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { useDocPermissions } from "../../composables/useDocPermissions";
import { memoizedState } from "../../utils/sharedState";
import { chooseLayout } from "./chooseLayout";
import { joinLayout } from "./joinLayout";
import type { FormLayoutsResponse, FormLayoutType } from "./types";

export interface UseFormLayoutOptions {
	doctype: MaybeRefOrGetter<string>;
	type: FormLayoutType;
	/** The live doc conditions evaluate against; the layout follows its edits. */
	doc?: Ref<Record<string, any>>;
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
		const tree = chooseLayout(response.layouts, doc) ?? response.fallback;

		const childMetas: Record<string, RawMetaField[]> = {};
		for (const [name, m] of Object.entries(metas.value))
			if (m.fields) childMetas[name] = m.fields;

		return joinLayout(tree, fields, { childMetas, fieldAccess });
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
