// The palette's places: Go to (sidebar rows, doctypes, apps, settings panes) and Create.
import { computed, shallowRef, type ComputedRef } from "vue";
import type { RouteLocation } from "vue-router";
import { runMethod } from "@framework/ui/api";
import { acts } from "@/acts/dispatcher";
import type { Boot, Navigation, NavigationItem } from "@/boot";
import { __ } from "@/i18n";
import { itemContext } from "@/navigation/context";
import { labelOf } from "@/navigation/registry";
import type { ItemContext } from "@/navigation/types";
import type { PaletteRow } from "./palette";
import type { PaletteContext, PaletteGroup } from "./paletteGroups";
import { rank } from "./paletteRanking";
import { SettingsAddressBook } from "./settingsAddress";
import { fetchPanes, type PanesReply } from "./settingsPanes";

export interface DoctypePlace {
	name: string;
	app: string;
	/** The doctype's own address, under its app's prefix. */
	route: string;
	can_create: boolean;
}

export interface PlacesReply {
	doctypes: DoctypePlace[];
	apps: { app: string; title: string; route: string }[];
	titles: Record<string, string>;
}

const GO_TO_CAP = 8;
const CREATE_CAP = 5;
const ROUTE_ICONS: Record<string, string> = {
	list: "lucide-list",
	record: "lucide-file-text",
};

/** A read the tab keeps once it answers; a failed one is asked again on the next open. */
class HeldRead<T> {
	readonly value = shallowRef<T | null>(null);
	private asking = false;

	ask(read: () => Promise<T>) {
		if (this.value.value || this.asking) return;
		this.asking = true;
		read()
			.then(
				(reply) => void (this.value.value = reply),
				(error) => console.error("[frappe] the palette could not read its places", error)
			)
			.finally(() => (this.asking = false));
	}
}

const places = new HeldRead<PlacesReply>();
const panes = new HeldRead<PanesReply>();

/** Asks for the places and the settings panes the tab does not hold yet. */
export function loadPlaces(boot: Boot) {
	places.ask(fetchPlaces);
	panes.ask(() => fetchPanes(boot));
}

export const goTo: PaletteGroup = {
	get label() {
		return __("Go to");
	},
	rows: (query, context) =>
		query.trim() ? rank(rowsFor(context).goTo.value, query).slice(0, GO_TO_CAP) : [],
};

export const create: PaletteGroup = {
	get label() {
		return __("Create");
	},
	rows: (query, context) =>
		query.trim() ? rank(rowsFor(context).create.value, query).slice(0, CREATE_CAP) : [],
};

/** In this prefix the router moves; another prefix is another document. */
export function openPlace(href: string, { boot, router }: PaletteContext) {
	const base = boot.shell_base;
	if (boot.app && (href === base || href.startsWith(`${base}/`)))
		router.push(href.slice(base.length) || "/");
	else window.location.assign(href);
}

async function fetchPlaces(): Promise<PlacesReply> {
	const envelope = await runMethod<PlacesReply>("frappe.shell.palette.places", {}, { http: "GET" });
	return envelope.data;
}

const built = new WeakMap<PaletteContext, PlaceRows>();

function rowsFor(context: PaletteContext): PlaceRows {
	let rows = built.get(context);
	if (!rows) built.set(context, (rows = new PlaceRows(context)));
	return rows;
}

/** One palette's place rows, rebuilt when a reply lands or the navigation is replaced. */
class PlaceRows {
	readonly goTo: ComputedRef<PaletteRow[]>;
	readonly create: ComputedRef<PaletteRow[]>;
	private readonly doctypes = computed(() => this.doctypeRows());
	private navigation: { from?: Navigation; rows: PaletteRow[] } = { rows: [] };

	constructor(private readonly context: PaletteContext) {
		const others = computed(() => [...this.doctypes.value, ...this.appRows(), ...this.paneRows()]);
		this.goTo = computed(() => [...this.sidebarRows(), ...others.value]);
		this.create = computed(() => this.createRows());
	}

	private doctypeRows(): PaletteRow[] {
		const reply = places.value.value;
		if (!reply) return [];
		const { addresses } = this.context;
		return reply.doctypes.map((doctype) => {
			const app = reply.titles[doctype.app] ?? doctype.app;
			const single = addresses.isSingle(doctype.name);
			return {
				id: `doctype:${doctype.name}`,
				label: __(doctype.name),
				description: app,
				keywords: [doctype.name, app],
				icon: single ? ROUTE_ICONS.record : ROUTE_ICONS.list,
				href: doctype.route,
				doctype: !single && this.opensRecordsAt(doctype.route) ? doctype.name : undefined,
				run: () => openPlace(doctype.route, this.context),
			};
		});
	}

	private appRows(): PaletteRow[] {
		return (places.value.value?.apps ?? []).map((app) => ({
			id: `app:${app.app}`,
			label: app.title,
			keywords: [app.app],
			icon: "lucide-layout-grid",
			href: app.route,
			run: () => openPlace(app.route, this.context),
		}));
	}

	private paneRows(): PaletteRow[] {
		const reply = panes.value.value;
		if (!reply) return [];
		const book = new SettingsAddressBook(reply, this.context.boot);
		return book.everyGroup().flatMap(({ prefix, panes: groupPanes }) =>
			groupPanes.map((pane) => ({
				id: `settings:${prefix}/${pane.key}`,
				label: __(pane.label),
				description: reply.titles[pane.app],
				keywords: [__("Settings")],
				icon: "lucide-settings",
				run: () => acts.perform("shell.open_settings", { prefix, pane: pane.key }),
			}))
		);
	}

	private createRows(): PaletteRow[] {
		const reply = places.value.value;
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

	// `boot.navigation` is replaced whole on a save and is not reactive, so its identity is the key.
	private sidebarRows(): PaletteRow[] {
		const navigation = this.context.boot.navigation;
		if (!navigation) return [];
		if (this.navigation.from !== navigation)
			this.navigation = { from: navigation, rows: this.navigationRows(navigation) };
		return this.navigation.rows;
	}

	/** This app's rail and sidebar rows that lead somewhere, one per address. */
	private navigationRows(navigation: Navigation): PaletteRow[] {
		const { boot, addresses, router } = this.context;
		const rows = new Map<string, PaletteRow>();
		for (const items of [...Object.values(navigation.sidebars), navigation.rail]) {
			const container = itemContext(boot, addresses, router, items, navigation.sidebars);
			for (const item of items) {
				const row = this.navigationRow(item, container);
				if (row?.href && !rows.has(row.href)) rows.set(row.href, row);
			}
		}
		return [...rows.values()];
	}

	private navigationRow(item: NavigationItem, container: ItemContext): PaletteRow | null {
		const rendering = container.renderingOf(item);
		if (!rendering || !("to" in rendering || "href" in rendering)) return null;
		const route = "to" in rendering ? this.context.router.resolve(rendering.to) : null;
		const href = route ? route.href : (rendering as { href: string }).href;
		const doctype = route && isList(route) ? this.context.addresses.doctypeOf(slugOf(route)) : null;
		return {
			id: `sidebar:${href}`,
			label: labelOf(item, container),
			description: this.context.boot.app_title,
			keywords: doctype ? [doctype] : undefined,
			icon: route ? ROUTE_ICONS[String(route.name)] ?? "lucide-app-window" : "lucide-link",
			href,
			doctype: doctype && this.opensRecordsAt(href) ? doctype : undefined,
			run: () => openPlace(href, this.context),
		};
	}

	/** Tab narrows only where this router opens the records it finds at their doctype's address. */
	private opensRecordsAt(href: string) {
		const { boot, router } = this.context;
		return router.hasRoute("record") && href.startsWith(`${boot.shell_base}/`);
	}
}

function isList(route: RouteLocation) {
	return route.name === "list" || route.name === "standard-list";
}

function slugOf(route: RouteLocation) {
	return String(route.params.doctype);
}
