// The view object the list page hands to a view type's renderer and to a replacement page.
import type { FilterCondition } from "@framework/ui/Filter";
import type { Sort } from "@framework/ui/SortBy";
import type { ComputedRef, Ref } from "vue";
import type { ViewLayer } from "./savedView";

/** A view's settings: one JSON object, whose keys belong to its type. */
export type ViewSettings = Readonly<Record<string, unknown>>;

export interface View {
	doctype: string;
	/** The saved view's key, or its type's name in lower case for the type's plain view. */
	key: string;
	/** The `View Type` record's name. */
	type: string;
	/** Null for a type's plain view. */
	layer: ViewLayer | null;
	/** The stored settings with the page's changes on top; the type's own keys are the renderer's. */
	settings: ComputedRef<ViewSettings>;
	/** With the URL query applied; written back to it. */
	filters: Ref<FilterCondition[]>;
	/** With the URL query applied; written back to it. Never empty once seeded. */
	sort: Ref<Sort[]>;
	/** True once meta, the stored settings and the URL are read into the state above. */
	seeded: ComputedRef<boolean>;
	/** True while a filter or a sort in the query, or a settings change not yet stored, sits on the view. */
	modified: ComputedRef<boolean>;
	/** Changes settings keys in page state; the plain view's row is written as well. */
	update: (patch: Record<string, unknown>) => void;
	/** True when the person's own row holds `key`. */
	customized: (key: string) => boolean;
	/** Clears the person's `key`, so the site's or the app's shows. */
	reset: (key: string) => Promise<void>;
}

/** A type's name as an address segment, a `pages.json` key and an act's surface. */
export function typeKey(type: string): string {
	return type.toLowerCase();
}
