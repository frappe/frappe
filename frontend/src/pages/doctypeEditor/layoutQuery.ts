// The layout the editor opens, in the address: `?layout=side-panel&row=<id>`.
import { watch } from "vue";
import { useRoute, useRouter, type LocationQuery } from "vue-router";
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import type { DesignCanvas } from "./designCanvas";
import type { LayoutRef } from "./workingLayouts";

const KEYS: Record<FormLayoutType, string> = {
	Details: "details",
	"Side Panel": "side-panel",
	"Quick Entry": "quick-entry",
	"New Record": "new-record",
};

/** Keeps the address on the open layout both ways; other query keys stay, and nothing reloads. */
export function useLayoutAddress(canvas: () => DesignCanvas | null) {
	const route = useRoute();
	const router = useRouter();
	watch([() => route.query.layout, () => route.query.row], () => canvas()?.open(layoutFromQuery(route.query)));
	watch(
		() => canvas()?.openLayout.value,
		(open) => {
			if (!open || (sameLayout(layoutFromQuery(route.query), open) && !route.query.from)) return;
			const { layout: _layout, row: _row, from: _from, ...rest } = route.query;
			void router.replace({ query: { ...rest, ...layoutQuery(open) } });
		},
	);
}

/** Opens the layout the address names; the new record page's link (`from=new-record`) may open Details instead. */
export function openFromAddress(canvas: DesignCanvas, query: LocationQuery) {
	const layout = layoutFromQuery(query);
	if (first(query.from) === "new-record") canvas.openForNewRecord(layout);
	else canvas.open(layout);
}

/** An unknown `layout` opens Details; no `row` opens the type's default. */
export function layoutFromQuery(query: LocationQuery): LayoutRef {
	const key = first(query.layout);
	const type = (Object.keys(KEYS) as FormLayoutType[]).find((each) => KEYS[each] === key) ?? "Details";
	const row = first(query.row);
	return row ? { type, id: row } : { type };
}

export function layoutQuery({ type, id }: LayoutRef): { layout: string; row?: string } {
	return id ? { layout: KEYS[type], row: id } : { layout: KEYS[type] };
}

export function sameLayout(one: LayoutRef, other: LayoutRef): boolean {
	return one.type === other.type && (one.id ?? "") === (other.id ?? "");
}

function first(value: LocationQuery[string] | undefined): string {
	return String((Array.isArray(value) ? value[0] : value) ?? "");
}
