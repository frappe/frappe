// The palette's places: Go to (doctypes, apps, this app's sidebar rows, settings panes), Create.
// The first open reads `places` and the settings panes, and the tab keeps both.
import { shallowRef } from "vue";
import type { RouteLocation } from "vue-router";
import { runMethod } from "@framework/ui/api";
import { acts } from "@/acts/dispatcher";
import type { Boot, NavigationItem } from "@/boot";
import { __ } from "@/i18n";
import { itemContext } from "@/navigation/context";
import { labelOf } from "@/navigation/registry";
import type { PaletteRow } from "./palette";
import type { PaletteContext, PaletteGroup } from "./paletteGroups";
import { rank } from "./paletteRanking";
import { SettingsAddressBook } from "./settingsAddress";
import { fetchPanes } from "./settingsPanes";

export interface DoctypePlace {
	name: string;
	app: string;
	/** The doctype's own address, under its app's prefix. */
	route: string;
	single: boolean;
	can_create: boolean;
}

export interface PlacesReply {
	doctypes: DoctypePlace[];
	apps: { app: string; title: string; route: string }[];
	/** Each doctype's app's title. */
	titles: Record<string, string>;
}

const GO_TO_CAP = 8;
const CREATE_CAP = 5;
const ROUTE_ICONS: Record<string, string> = {
	list: "lucide-list",
	record: "lucide-file-text",
};

const held = shallowRef<PlacesReply | null>(null);
const panes = shallowRef<PaletteRow[]>([]);
let asking: Promise<void> | null = null;

/** Reads the places and the settings panes once per tab; after a failure, the next open asks. */
export function loadPlaces(boot: Boot) {
	asking ??= Promise.all([fetchPlaces(), fetchPanes(boot)]).then(
		([places, reply]) => {
			held.value = places;
			panes.value = paneRows(new SettingsAddressBook(reply, boot), reply.titles);
		},
		(error) => {
			asking = null;
			console.error("[frappe] the palette could not read its places", error);
		}
	);
}

export const goTo: PaletteGroup = {
	get label() {
		return __("Go to");
	},
	rows: (query, context) =>
		query.trim()
			? rank(placeRows(context), query).slice(0, GO_TO_CAP)
			: [],
};

export const create: PaletteGroup = {
	get label() {
		return __("Create");
	},
	rows: (query) => (query.trim() ? rank(createRows(), query).slice(0, CREATE_CAP) : []),
};

/** In this prefix the router moves; another prefix is another document. */
export function openPlace(href: string, { boot, router }: PaletteContext) {
	const base = `${boot.shell_base}/`;
	if (boot.app && href.startsWith(base)) router.push(href.slice(boot.shell_base.length));
	else window.location.assign(href);
}

async function fetchPlaces(): Promise<PlacesReply> {
	const envelope = await runMethod<PlacesReply>("frappe.shell.palette.places", {}, { http: "GET" });
	return envelope.data;
}

function placeRows(context: PaletteContext): PaletteRow[] {
	return [...sidebarRows(context), ...doctypeRows(context), ...appRows(context), ...panes.value];
}

function doctypeRows(context: PaletteContext): PaletteRow[] {
	const reply = held.value;
	if (!reply) return [];
	return reply.doctypes.map((doctype) => {
		const app = reply.titles[doctype.app] ?? doctype.app;
		return {
			id: `doctype:${doctype.name}`,
			label: __(doctype.name),
			description: app,
			keywords: [doctype.name, app],
			icon: doctype.single ? ROUTE_ICONS.record : ROUTE_ICONS.list,
			href: doctype.route,
			doctype: doctype.single || !opensRecords(context) ? undefined : doctype.name,
			run: () => openPlace(doctype.route, context),
		};
	});
}

function appRows(context: PaletteContext): PaletteRow[] {
	return (held.value?.apps ?? []).map((app) => ({
		id: `app:${app.app}`,
		label: app.title,
		keywords: [app.app],
		icon: "lucide-layout-grid",
		href: app.route,
		run: () => openPlace(app.route, context),
	}));
}

function createRows(): PaletteRow[] {
	const reply = held.value;
	if (!reply) return [];
	return reply.doctypes
		.filter((doctype) => doctype.can_create)
		.map((doctype) => {
			const app = reply.titles[doctype.app] ?? doctype.app;
			return {
				id: `create:${doctype.name}`,
				label: __("New {0}", [__(doctype.name)]),
				description: app,
				keywords: [doctype.name, app],
				icon: "lucide-plus",
				run: () => acts.perform("shell.create", doctype.name),
			};
		});
}

let sidebarMemo: { navigation: Boot["navigation"]; rows: PaletteRow[] } | null = null;

/** This app's rail and sidebar rows that lead somewhere, one per address, once per navigation. */
function sidebarRows(context: PaletteContext): PaletteRow[] {
	const navigation = context.boot.navigation;
	if (!navigation) return [];
	if (sidebarMemo?.navigation !== navigation)
		sidebarMemo = { navigation, rows: navigationRows(navigation, context) };
	return sidebarMemo.rows;
}

function navigationRows(navigation: NonNullable<Boot["navigation"]>, context: PaletteContext) {
	const rows = new Map<string, PaletteRow>();
	const lists = [...Object.values(navigation.sidebars), navigation.rail];
	for (const items of lists) {
		const { boot, addresses, router } = context;
		const itemsContext = itemContext(boot, addresses, router, items, navigation.sidebars);
		for (const item of items) {
			const row = navigationRow(item, itemsContext, context);
			if (row && !rows.has(row.href!)) rows.set(row.href!, row);
		}
	}
	return [...rows.values()];
}

function navigationRow(
	item: NavigationItem,
	itemsContext: ReturnType<typeof itemContext>,
	context: PaletteContext
): PaletteRow | null {
	const rendering = itemsContext.renderingOf(item);
	if (!rendering || !("to" in rendering || "href" in rendering)) return null;
	const route = "to" in rendering ? context.router.resolve(rendering.to) : null;
	const href = route ? route.href : (rendering as { href: string }).href;
	const doctype =
		route && isList(route) ? context.addresses.doctypeOf(String(route.params.doctype)) : null;
	return {
		id: `sidebar:${href}`,
		label: labelOf(item, itemsContext),
		description: context.boot.app_title,
		keywords: doctype ? [doctype] : undefined,
		icon: route ? ROUTE_ICONS[String(route.name)] ?? "lucide-app-window" : "lucide-link",
		href,
		doctype: doctype && opensRecords(context) ? doctype : undefined,
		run: () => openPlace(href, context),
	};
}

function paneRows(book: SettingsAddressBook, titles: Record<string, string>): PaletteRow[] {
	return book.everyGroup().flatMap(({ prefix, panes }) =>
		panes.map((pane) => ({
			id: `settings:${prefix}/${pane.key}`,
			label: __(pane.label),
			description: titles[pane.app],
			keywords: [__("Settings")],
			icon: "lucide-settings",
			run: () => acts.perform("shell.open_settings", { prefix, pane: pane.key }),
		}))
	);
}

function isList(route: RouteLocation) {
	return route.name === "list" || route.name === "standard-list";
}

/** Tab narrows only where the router can open a record it finds; the index has no record route. */
function opensRecords({ router }: PaletteContext) {
	return router.hasRoute("record");
}
