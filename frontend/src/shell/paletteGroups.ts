// The palette's groups in their fixed order, and the rows pinned below the list.
import type { Router } from "vue-router";
import { acts, type AvailableAct } from "@/acts/dispatcher";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { pageRows, type PaletteRow } from "./palette";
import { askFlow } from "./paletteFlow";
import { create, goTo, openPlace } from "./palettePlaces";
import { rank } from "./paletteRanking";
import { findRow, records } from "./paletteRecords";
import { recents, type Recent } from "./recents";

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
const RECENT_ICONS: Record<Recent["kind"], string> = {
	record: "lucide-file-text",
	list: "lucide-list",
	page: "lucide-app-window",
};

const recent: PaletteGroup = {
	get label() {
		return __("Recent");
	},
	rows: (query, context) =>
		query.trim() ? [] : recents.list().slice(0, RECENT_CAP).map((one) => recentRow(one, context)),
};

const thisPage: PaletteGroup = {
	get label() {
		return __("This page");
	},
	rows: (query) => rank([...actRows((act) => !isShellAct(act)), ...pageRows()], query),
};

const desk: PaletteGroup = {
	get label() {
		return __("Desk");
	},
	rows: (query, context) =>
		query.trim() ? rank(actRows(isShellAct, context.boot), query) : [],
};

export const paletteGroups: PaletteGroup[] = [recent, thisPage, desk, goTo, create, records];

/** Rows below the scrolling list, which never scroll away; the arrow keys reach them last. */
export const pinnedRows: PaletteGroup["rows"][] = [findRow, askFlow];

function recentRow(one: Recent, context: PaletteContext): PaletteRow {
	return {
		id: `recent:${one.href}`,
		label: one.label,
		description: one.kind === "record" && one.description ? __(one.description) : one.description,
		icon: RECENT_ICONS[one.kind],
		href: one.href,
		run: () => openPlace(one.href, context),
	};
}

/** The acts available now that the palette may show. */
function actRows(where: (act: AvailableAct) => boolean, boot?: Boot): PaletteRow[] {
	return acts
		.available()
		.filter((act) => act.palette !== false && !act.argument && act.label && where(act))
		.map((act) => {
			const app = boot && appOf(act, boot);
			return {
				id: `act:${act.name}`,
				label: act.label!,
				icon: act.icon,
				key: act.key,
				description: app,
				keywords: app ? [app] : undefined,
				run: () => acts.perform(act.name),
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
