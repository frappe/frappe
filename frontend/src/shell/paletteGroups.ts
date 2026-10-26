// The palette's groups in their fixed order, and the rows pinned below the list. A later group
// or pinned row is one more entry in its list; each one builds its own rows.
import type { Router } from "vue-router";
import { acts, type AvailableAct } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import { pageRows, type PaletteRow } from "./palette";
import { rank } from "./paletteRanking";
import { recents, type Recent } from "./recents";

export interface PaletteContext {
	boot: Boot;
	router: Router;
}

export interface PaletteGroup {
	label: string;
	/** Its rows for the query, ranked and capped; none hides the group. */
	rows: (query: string, context: PaletteContext) => PaletteRow[];
}

const RECENT_CAP = 5;
const RECENT_ICONS: Record<Recent["kind"], string> = {
	record: "lucide-file-text",
	list: "lucide-list",
	page: "lucide-app-window",
};

const recent: PaletteGroup = {
	label: "Recent",
	rows: (query, context) =>
		query.trim() ? [] : recents.list().slice(0, RECENT_CAP).map((one) => recentRow(one, context)),
};

const thisPage: PaletteGroup = {
	label: "This page",
	rows: (query) => rank([...actRows((act) => !isShellAct(act)), ...pageRows()], query),
};

const desk: PaletteGroup = {
	label: "Desk",
	rows: (query, context) =>
		query.trim() ? rank(actRows(isShellAct, context.boot), query) : [],
};

export const paletteGroups: PaletteGroup[] = [recent, thisPage, desk];

/** Rows below the scrolling list, which never scroll away; the arrow keys reach them last. */
export const pinnedRows: PaletteGroup["rows"][] = [];

function recentRow(one: Recent, context: PaletteContext): PaletteRow {
	return {
		id: `recent:${one.href}`,
		label: one.label,
		description: one.description,
		icon: RECENT_ICONS[one.kind],
		href: one.href,
		run: () => open(one.href, context),
	};
}

/** The acts available now that the palette may show; an act asking for a value waits for its step. */
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

/** In this prefix the router moves; another prefix is another document. */
function open(href: string, { boot, router }: PaletteContext) {
	const base = `${boot.shell_base}/`;
	if (boot.app && href.startsWith(base)) router.push(href.slice(boot.shell_base.length));
	else window.location.assign(href);
}
