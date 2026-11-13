// The layout crumb's menu: each layout type the DocType has, where its layout comes from, the
// conditional layouts under it, and the acts on the open one.
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import { __ } from "@/i18n";
import { workingState, type WorkingState } from "./editorModel";
import type { LayoutSource } from "./editorSource";
import { newLayoutId } from "./layoutActs";
import { typeLabel } from "./layoutNames";
import { EditRefused } from "./layoutTree";
import { baseSource, layoutOf, typeRefusal, type LayoutRef, type WorkingLayout } from "./workingLayouts";

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

export interface ResetWording {
	title: string;
	confirmLabel: string;
	actLabel: string;
}

export interface ResetSummary {
	removes: { name: string; condition: string | null }[];
	restores: { name: string; condition: string | null }[];
	/** The badge of what the type goes back to when the app has no layout of it. */
	fallback: string | null;
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

/** Why "Add a layout" cannot add this one, or `null`; every type has a default, if only a stand-in, so it needs a condition. */
export function addLayoutRefusal(working: WorkingState, layout: NewLayout): string | null {
	const refused = typeRefusal(working, layout.type);
	if (refused) return __(refused.template, refused.args);
	if (!layout.condition) {
		return __("{0} has one default layout: edit that one, or give this one a condition.", [typeLabel(layout.type)]);
	}
	try {
		workingState(working, [{ act: "layouts.add", id: newLayoutId(), ...layout }]);
		return null;
	} catch (error) {
		if (error instanceof EditRefused) return __(error.template, error.args);
		throw error;
	}
}

/** What Reset to app layout removes from a type and what comes back after the save. */
export function resetSummary(working: WorkingState, type: FormLayoutType): ResetSummary {
	const of = working.layouts[type];
	const row = (layout: WorkingLayout) => ({ name: layout.title || layout.condition || typeLabel(type), condition: layout.condition });
	return {
		removes: (of?.layouts ?? []).map(row),
		restores: (of?.app ?? []).map(row),
		fallback: of?.app.length ? null : badge(baseSource(working, type)),
	};
}

/** The reset's menu act, confirm title and button, named by what comes back. */
export function resetWording(working: WorkingState, type: FormLayoutType): ResetWording {
	const label = typeLabel(type);
	const source = baseSource(working, type);
	if (source === "app") {
		return { title: __("Reset to app layout?"), confirmLabel: __("Reset to app layout"), actLabel: __("Reset to app layout") };
	}
	if (source === "fallback") {
		return {
			title: __("Reset to the layout from DocType fields?"),
			confirmLabel: __("Reset"),
			actLabel: __("Reset to DocType fields"),
		};
	}
	if (source === "same as Details") {
		return {
			title: __("Reset {0} to the Details layout?", [label]),
			confirmLabel: __("Reset"),
			actLabel: __("Reset to Details layout"),
		};
	}
	return { title: __("Remove the {0} site layouts?", [label]), confirmLabel: __("Remove"), actLabel: __("Remove site layouts") };
}

/** `opened` is the open layout when it is of this type. */
function menuType(working: WorkingState, type: FormLayoutType, opened: WorkingLayout | null): MenuType {
	const fallback = layoutOf(working, { type })!;
	const conditional = (working.layouts[type]?.layouts ?? []).filter((layout) => layout.condition);
	return {
		type,
		label: typeLabel(type),
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
		name: layout.title || layout.condition || typeLabel(type),
		where: layout.condition ? __("{0} when {1}", [where, layout.condition]) : where,
		acts,
	};
}

function badge(source: LayoutSource): string {
	return BADGES[source]();
}

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
