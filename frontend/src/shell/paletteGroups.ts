// The palette's groups in their fixed order, the rows pinned below the list, and the one
// query-to-rows step that the palette and the index's filter box both draw from.
import type { Router } from "vue-router";
import { acts, type AvailableAct } from "@/acts/dispatcher";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { openArgumentStep, pageRows, type PaletteRow } from "./palette";
import { askFlow } from "./paletteFlow";
import { create, goTo, loadPlaces, openPlace } from "./palettePlaces";
import { rank } from "./paletteRanking";
import { findRow, records } from "./paletteRecords";
import { recentVisits, type RecentVisit } from "./recentVisits";

export interface PaletteContext {
	boot: Boot;
	router: Router;
	addresses: Addresses;
}

export interface PaletteGroup {
	/** Read at each draw, so it is translated once the messages have loaded. */
	readonly label: string;
	/** Its rows for the query, ranked and capped; none hides the group. */
	rows: (query: string, context: PaletteContext) => PaletteRow[];
	/** A group that asks the server hears each change of query here. */
	follow?: (query: string, context: PaletteContext) => void;
}

const RECENT_CAP = 5;
const RECENT_ICONS: Record<RecentVisit["kind"], string> = {
	record: "lucide-file-text",
	list: "lucide-list",
	view: "lucide-list-filter",
};

const recent: PaletteGroup = {
	get label() {
		return __("Recent");
	},
	rows: (query, context) =>
		query.trim() ? [] : recentVisits.list().slice(0, RECENT_CAP).map((one) => recentRow(one, context)),
};

const thisPage: PaletteGroup = {
	get label() {
		return __("This page");
	},
	rows: (query) => rank([...actRows((act) => !isShellAct(act)), ...pageRows()], query),
};

export const desk: PaletteGroup = {
	get label() {
		return __("Desk");
	},
	rows: (query, context) =>
		query.trim() ? rank(actRows(isShellAct, context.boot), query) : [],
};

export const paletteGroups: PaletteGroup[] = [recent, thisPage, desk, goTo, create, records];

/** Rows below the scrolling list, which never scroll away; the arrow keys reach them last. */
export const pinnedRows: PaletteGroup["rows"][] = [findRow, askFlow];

/** A group as drawn: its label and its rows for the query. */
export interface DrawnGroup {
	label: string;
	rows: PaletteRow[];
}

/** The groups a search draws, in order, and the rows it pins after them. */
export interface PaletteSource {
	groups: PaletteGroup[];
	pinned: PaletteGroup["rows"][];
}

/** One context's search over a source: the palette's own by default. */
export class PaletteSearch {
	constructor(
		private readonly context: PaletteContext,
		private readonly source: PaletteSource = { groups: paletteGroups, pinned: pinnedRows }
	) {}

	/** The groups that have rows for `query`, in the source's order. */
	groups(query: string): DrawnGroup[] {
		return this.source.groups
			.map((group) => ({ label: group.label, rows: group.rows(query, this.context) }))
			.filter((group) => group.rows.length);
	}

	pinned(query: string): PaletteRow[] {
		return this.source.pinned.flatMap((rows) => rows(query, this.context));
	}

	/** Hands the query to the groups that ask the server; an empty one stops their asking. */
	follow(query: string) {
		this.source.groups.forEach((group) => group.follow?.(query, this.context));
	}

	/** Asks for the places and panes Go to and Create draw from, if the tab lacks them. */
	load(): Promise<unknown> {
		return loadPlaces(this.context.boot);
	}
}

function recentRow(one: RecentVisit, context: PaletteContext): PaletteRow {
	return {
		id: `recent:${one.route}`,
		label: one.title,
		description: one.description,
		icon: RECENT_ICONS[one.kind],
		href: one.route,
		run: () => openPlace(one.route, context),
	};
}

/** The acts available now that the palette may show. */
function actRows(where: (act: AvailableAct) => boolean, boot?: Boot): PaletteRow[] {
	return acts
		.available()
		.filter((act) => act.palette !== false && act.label && where(act))
		.map((act) => {
			const app = boot && appOf(act, boot);
			return {
				id: `act:${act.name}`,
				label: act.label!,
				icon: act.icon,
				key: act.key,
				description: app,
				keywords: app ? [app] : undefined,
				stays: Boolean(act.argument),
				run: () => (act.argument ? openArgumentStep(act.name) : acts.perform(act.name)),
			};
		});
}

function isShellAct(act: AvailableAct) {
	return act.name.startsWith("shell.");
}

/** An app's shell act is `shell.<app>.<item>`; the framework's own have no app. */
function appOf(act: AvailableAct, boot: Boot): string | undefined {
	const [, app, item] = act.name.split(".");
	if (!item) return undefined;
	return app === boot.app ? boot.app_title ?? app : app;
}
