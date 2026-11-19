// The client half of arranging: the editor reads a whole level, edits a draft and sends back
// the containers it changed. Nothing here is a store; a save returns the prefix's navigation
// and the caller swaps it in.

import { runMethod } from "@framework/ui/api";
import type { Navigation, NavigationItem } from "@/boot";

export type Scope = "user" | "site";
export type Origin = "app" | "site" | "user";

/** A wire row plus what only the editor's read carries. None of the markers is ever stored. */
export type EditorRow = NavigationItem & {
	hidden?: 1;
	hidden_by?: "site" | "user";
	no_access?: 1;
	view_deleted?: 1;
};

/** `get_arrangements`'s answer. */
export type Arrangements = {
	version: string;
	can_edit_site: boolean;
	/** This level has stored a rail or a sidebar of the app, so Reset to default has something to undo. */
	has_saved: boolean;
	navigation_layouts: Record<string, string>;
	rail: EditorRow[];
	sidebars: Record<string, EditorRow[]>;
};

/** `get_default_arrangements`'s answer: the rows of the level below. */
export type Defaults = { rail: EditorRow[]; sidebars: Record<string, EditorRow[]> };

/** What `save_arrangements` takes: the whole ordered list of each container that changed. */
export type Payload = { rail?: EditorRow[]; sidebars?: Record<string, EditorRow[]> };

export async function fetchArrangements(app: string, scope: Scope): Promise<Arrangements> {
	const response = await runMethod<Arrangements>(
		"frappe.shell.arrangement.get_arrangements",
		{ app, scope },
		{ http: "GET" }
	);
	return response.data;
}

/** The level below's rows, read when Reset to default is clicked; nothing is stored. */
export async function fetchDefaultArrangements(app: string, scope: Scope): Promise<Defaults> {
	const response = await runMethod<Defaults>(
		"frappe.shell.arrangement.get_default_arrangements",
		{ app, scope },
		{ http: "GET" }
	);
	return response.data;
}

/**
 * `save_arrangements` returns the navigation, not the new version: a second save needs
 * `fetchArrangements` again.
 */
export async function saveArrangements(
	app: string,
	scope: Scope,
	containers: Payload,
	version: string
): Promise<Navigation> {
	const response = await runMethod<Navigation>("frappe.shell.arrangement.save_arrangements", {
		app,
		scope,
		containers,
		version,
	});
	return response.data;
}

export async function saveNavigationLayout(
	app: string,
	navigationLayout: string,
	scope: Scope
): Promise<Navigation> {
	const response = await runMethod<Navigation>("frappe.shell.arrangement.save_navigation_layout", {
		app,
		navigation_layout: navigationLayout,
		scope,
	});
	return response.data;
}
