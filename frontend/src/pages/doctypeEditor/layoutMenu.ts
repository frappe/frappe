// The layout crumb's menu: each layout type the DocType has, where its layout comes from, the
// conditional layouts under it, and the acts on the open one.
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import { __ } from "@/i18n";
import { workingState, type WorkingState } from "./editorModel";
import type { LayoutSource } from "./editorSource";
import { EditRefused } from "./layoutTree";
import { layoutOf, type LayoutRef, type WorkingLayout } from "./workingLayouts";

export type OpenLayoutAct = "edit_condition" | "rename" | "reset_to_app" | "delete";

export interface MenuLayout {
	ref: LayoutRef;
	/** The title, else the condition. */
	name: string;
	badge: string;
	open: boolean;
}

export interface MenuType {
	type: FormLayoutType;
	label: string;
	icon: string;
	badge: string;
	/** The type's default. */
	ref: LayoutRef;
	open: boolean;
	/** Its conditional layouts. */
	layouts: MenuLayout[];
}

export interface LayoutMenu {
	types: MenuType[];
	/** Why the menu lists fewer types. */
	note: string | null;
	/** The open layout's acts; `null` when it has none. */
	open: { name: string; where: string; acts: OpenLayoutAct[] } | null;
}

export interface NewLayout {
	type: FormLayoutType;
	title?: string;
	condition?: string;
}

export function layoutMenu(working: WorkingState, open: LayoutRef): LayoutMenu {
	const opened = layoutOf(working, open);
	const types = (Object.keys(working.layouts) as FormLayoutType[]).map((type) =>
		menuType(working, type, open.type === type ? opened : null),
	);
	return {
		types,
		note: working.definition.istable ? __("A child table's rows use Details only") : null,
		open: opened ? openActs(working, open.type, opened) : null,
	};
}

/** What the layout crumb names: the open type's label, or the open conditional layout's name. */
export function openLayoutName(menu: LayoutMenu): string {
	for (const type of menu.types) {
		if (type.open) return type.label;
		const layout = type.layouts.find((one) => one.open);
		if (layout) return layout.name;
	}
	return LABELS.Details();
}

/** Why "Add a layout" cannot add this one: the save's own refusal, or `null`. */
export function addLayoutRefusal(working: WorkingState, layout: NewLayout): string | null {
	try {
		workingState(working, [{ act: "layouts.add", id: newLayoutId(), ...layout }]);
		return null;
	} catch (error) {
		if (error instanceof EditRefused) return __(error.template, error.args);
		throw error;
	}
}

/** An id the server takes for a new layout until its save names the row. */
export function newLayoutId(): string {
	return `new-${Math.random().toString(36).slice(2, 10)}`;
}

/** `opened` is the open layout when it is of this type. */
function menuType(working: WorkingState, type: FormLayoutType, opened: WorkingLayout | null): MenuType {
	const fallback = layoutOf(working, { type })!;
	const conditional = (working.layouts[type]?.layouts ?? []).filter((layout) => layout.condition);
	return {
		type,
		label: LABELS[type](),
		icon: ICONS[type],
		badge: badge(fallback.source),
		ref: { type },
		open: Boolean(opened && !opened.condition),
		layouts: conditional.map((layout) => ({
			ref: { type, id: layout.id },
			name: layout.title || layout.condition!,
			badge: badge(layout.source),
			open: layout === opened,
		})),
	};
}

function openActs(working: WorkingState, type: FormLayoutType, layout: WorkingLayout): LayoutMenu["open"] {
	const acts: OpenLayoutAct[] = layout.condition ? ["edit_condition", "rename"] : [];
	if (working.mode === "Customize" && layout.source === "site") acts.push("reset_to_app");
	if (layout.condition) acts.push("delete");
	if (!acts.length) return null;
	const where = WHERE[type]();
	return {
		name: layout.title || layout.condition || LABELS[type](),
		where: layout.condition ? __("{0} when {1}", [where, layout.condition]) : where,
		acts,
	};
}

function badge(source: LayoutSource): string {
	return BADGES[source]();
}

const LABELS: Record<FormLayoutType, () => string> = {
	Details: () => __("Details"),
	"Side Panel": () => __("Side panel"),
	"Quick Entry": () => __("Quick entry"),
	"New Record": () => __("New record"),
};

const ICONS: Record<FormLayoutType, string> = {
	Details: "lucide-file-text",
	"Side Panel": "lucide-panel-right",
	"Quick Entry": "lucide-app-window",
	"New Record": "lucide-file-plus",
};

const WHERE: Record<FormLayoutType, () => string> = {
	Details: () => __("Shows in the record page's main column"),
	"Side Panel": () => __("Shows on the record page's right side"),
	"Quick Entry": () => __("Shows in the Create dialog"),
	"New Record": () => __("Shows on a new record's page until its first save"),
};

const BADGES: Record<LayoutSource, () => string> = {
	app: () => __("App layout"),
	site: () => __("Site layout"),
	fallback: () => __("From DocType fields"),
	none: () => __("Not set up"),
	"same as Details": () => __("Same as Details"),
};
