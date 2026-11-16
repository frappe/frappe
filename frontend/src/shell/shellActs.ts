// The shell surface, `shell`: the acts that outlive a page. The rail's app menu, the avatar menu
// and the sidebar's edge draw from it, so each entry is declared once.
import { onScopeDispose } from "vue";
import { isNavigationFailure, NavigationFailureType, type Router } from "vue-router";
import { toast, useColorScheme, type ColorScheme } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import type { FieldMeta } from "@framework/ui/fields/types";
import { acts, type ActItem, type AvailableAct } from "@/acts/dispatcher";
import { doctypeRight } from "@/acts/doctypeRight";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { hrefFor } from "@/router/recordLink";
import { routeFor } from "@/router/routeFor";
import { useAppActs } from "./appActs";
import { kindOf } from "./fieldActions";
import { openCreate, type CreatedDoc, type CreateOptions } from "./create";
import { shellDialog, type ShellDialog } from "./dialog";
import { useRealtime, type ShellRealtime } from "./realtime";
import type { StandingWindowHandle } from "./standingWindows";
import { dialogEntries } from "./dialogActs";
import { navSide } from "./navigationSide";
import { loadDocument } from "./tabKeepAlive";
import { resetWindowHandles, windowHandleOf } from "./windowHandles";

/** Opens `#settings/<prefix>/<pane>/<block>`; each segment is optional, in order. */
export type OpenSettings = (prefix?: string, pane?: string, block?: string) => void;

/** The record page the reader is on: its doctype and name, the draft, and its fields' labels and types (a Data field of Phone options reads Phone). */
export interface ShellRecord {
	doctype: string;
	name: string;
	doc: Record<string, any>;
	fields: { fieldname: string; label: string; fieldtype: string }[];
}

/** What a shell act's `run` and `argument.options` receive. */
export interface Shell {
	router: Router;
	toast: { success: (message: string) => void; error: (message: string) => void; info: (message: string) => void };
	call: (method: string, params?: Record<string, any>) => Promise<any>;
	run: (name: string, value?: unknown) => Promise<unknown>;
	create: (doctype: string, options?: CreateOptions) => Promise<CreatedDoc | null>;
	/** Opens a record, a doctype's list or a saved view: `shell.open('ToDo')`, `shell.open('ToDo', name)`, `shell.open('ToDo', null, { view })`. */
	open: (doctype: string, name?: string | null, options?: { view?: string }) => Promise<void>;
	/** The address of a record or list, for a plain `<a>`; `null` when the doctype has none. */
	href: (doctype: string, name?: string | null) => string | null;
	openSettings: OpenSettings;
	dialog: ShellDialog;
	/** The saved record open on the page, else `null`: a list, a new record or no page. */
	record: () => ShellRecord | null;
	/** The standing window of `app`, from before its shell hook attaches it. */
	windowOf: (app: string) => StandingWindowHandle;
	realtime: ShellRealtime;
}

/** `shell.create`'s value: a doctype, or a doctype with the values its record starts with. */
type CreateValue = string | { doctype: string; values?: Record<string, any> };

/** `shell.open`'s value: what `routeFor` takes. */
interface OpenValue {
	doctype: string;
	name?: string | null;
	view?: string;
}

/** `shell.open_settings`'s value: the settings address's segments; none opens the first pane. */
interface SettingsAddress {
	prefix?: string;
	pane?: string;
	block?: string;
}

interface ShellActsHost {
	boot: Boot;
	router: Router;
	openSettings: OpenSettings;
	openAbout: () => void;
	confirmLogout: () => void;
	/** The rail's acts, present only while the rail draws. */
	rail?: RailActsHost;
}

interface RailActsHost {
	customize: () => void;
	/** The link to the page as shown; without it there is no Copy link. */
	shareLink?: () => string;
	/** Whether the open sidebar is collapsed, or `null` while no sidebar shows. */
	sidebarCollapsed: () => boolean | null;
	toggleSidebar: () => void;
}

/** The schemes `shell.theme` takes, labelled in the reader's language. */
export function colorSchemes(): { value: ColorScheme; label: string; icon: string }[] {
	return [
		{ value: "light", label: __("Light"), icon: "lucide-sun" },
		{ value: "dark", label: __("Dark"), icon: "lucide-moon" },
		{ value: "system", label: __("System"), icon: "lucide-monitor" },
	];
}

/** Registers the `shell` surface for the shell's life; the palette waits on `appActsPending`. */
export function useShellActs(host: ShellActsHost) {
	const shell = shellFor(host, useRealtime());
	const appActs = useAppActs();
	const { setColorScheme } = useColorScheme();
	const release = acts.register({
		surfaces: {
			shell: () =>
				[...shellItems(host, setColorScheme), ...appActs.items()].map((item) => ({
					item,
					hidden: false,
				})),
			dialog: dialogEntries,
		},
		context: () => shell,
		passes: (right) => typeof right !== "string" && doctypeRight.passes(right),
		settled: (right) => (typeof right === "string" ? undefined : doctypeRight.settled(right)),
		loading: (name) => (isAppAct(name) ? appActs.pending() : undefined),
		loads: (name) => isAppAct(name) && appActs.loading(),
		hold: async (work) => work(),
		failed: (error) => void toast.error(error instanceof Error ? error.message : String(error)),
	});
	onScopeDispose(release);
	onScopeDispose(resetWindowHandles);
	return { appActsPending: appActs.pending, shell };
}

/** The shell act `name` while a menu draws it: the one rule for whether a shell entry is drawn. */
export function shellAct(name: string): AvailableAct | undefined {
	return acts.find(`shell.${name}`);
}

/** The menu rows that run the named shell acts, in order, for those drawn now. */
export function shellMenu(names: string[]): ShellMenuOption[] {
	return names.flatMap((name) => {
		const act = shellAct(name);
		return act ? [{ label: act.label!, icon: act.icon, onClick: () => void acts.perform(act.name) }] : [];
	});
}

interface ShellMenuOption {
	label: string;
	icon?: string;
	onClick: () => void;
}

/** An app's act is `shell.<app>.<item>`; the shell's own are `shell.<item>`. */
function isAppAct(name: string) {
	return name.split(".").length > 2;
}

function shellFor(host: ShellActsHost, realtime: ShellRealtime): Shell {
	return {
		router: host.router,
		toast: {
			success: (message) => toast.success(message),
			error: (message) => toast.error(message),
			info: (message) => toast.info(message),
		},
		call: (method, params) => runMethod(method, params).then((envelope) => envelope.data),
		run: (name, value) => acts.run(name, value),
		create: (doctype, options) => openCreate(doctype, options),
		open: (doctype, name, options) => acts.run("shell.open", { doctype, name, view: options?.view }) as Promise<void>,
		href: (doctype, name) => hrefFor(host.router, doctype, name),
		openSettings: host.openSettings,
		dialog: shellDialog(),
		record: openRecord,
		windowOf: windowHandleOf,
		realtime,
	};
}

/** The parts of the record page's `page` that `shell.record` reads. */
interface OpenPage {
	doctype: string;
	docname: string;
	doc: Record<string, any>;
	isNew: boolean;
	meta: { fields?: FieldMeta[] } | null;
}

// The record page registers its acts on the `header` surface, with the page as their context.
export function openRecord(): ShellRecord | null {
	const page = acts.contextOf("header") as OpenPage | undefined;
	if (!page?.doc || page.isNew || !page.docname) return null;
	const fields = (page.meta?.fields ?? []).map((field) => ({
		fieldname: field.fieldname,
		label: field.label ?? field.fieldname,
		fieldtype: kindOf(field),
	}));
	return { doctype: page.doctype, name: page.docname, doc: page.doc, fields };
}

export function shellItems(
	host: ShellActsHost,
	setColorScheme: (scheme: ColorScheme) => void
): ActItem<Shell>[] {
	return [
		...(host.rail ? railItems(host.rail) : []),
		openSettingsItem(host.boot),
		{ name: "about", asks: ["dialog"], label: __("About"), icon: "lucide-info", run: () => host.openAbout() },
		...personItems(host, setColorScheme),
		createItem(),
		openItem(),
		backItem(),
	];
}

function railItems(rail: RailActsHost): ActItem<Shell>[] {
	const items: ActItem<Shell>[] = [
		{
			name: "all_apps",
			label: __("All apps"),
			icon: "lucide-layout-grid",
			run: () => leave("/apps"),
		},
		{
			name: "customize_sidebar",
			asks: ["dialog"],
			label: __("Customize navigation"),
			icon: "lucide-settings-2",
			run: () => rail.customize(),
		},
	];
	const { shareLink } = rail;
	if (shareLink)
		items.push({
			name: "copy_link",
			label: __("Copy link"),
			icon: "lucide-link",
			run: () => copyLink(shareLink()),
		});
	const collapsed = rail.sidebarCollapsed();
	if (collapsed !== null)
		items.push({
			name: "toggle_sidebar",
			label: collapsed ? __("Expand sidebar") : __("Collapse sidebar"),
			icon: `lucide-panel-${navSide()}-${collapsed ? "open" : "close"}`,
			run: () => rail.toggleSidebar(),
		});
	return items;
}

function openSettingsItem(boot: Boot): ActItem<Shell> {
	return {
		name: "open_settings",
		asks: ["picker"],
		label: __("Settings"),
		icon: "lucide-settings",
		argument: {
			label: __("Settings panes"),
			options: () => import("./palettePlaces").then((places) => places.paneOptions(boot)),
		},
		run: (shell, address?: SettingsAddress) => shell.openSettings(...segmentsOf(address)),
	};
}

/** The address's segments in order, with no empty ones after the last given. */
function segmentsOf({ prefix, pane, block }: SettingsAddress = {}) {
	const segments = [prefix, pane, block];
	while (segments.length && segments[segments.length - 1] === undefined) segments.pop();
	return segments;
}

function createItem(): ActItem<Shell> {
	return {
		name: "create",
		asks: ["picker", "dialog"],
		label: __("Create"),
		icon: "lucide-plus",
		argument: {
			label: __("DocTypes"),
			options: () => import("./palettePlaces").then((places) => places.createOptions()),
		},
		run: (shell, value: CreateValue) => {
			const { doctype, values } =
				typeof value === "string" ? { doctype: value, values: undefined } : value;
			return shell.create(doctype, { values });
		},
	};
}

function openItem(): ActItem<Shell> {
	return {
		name: "open",
		asks: ["confirm"],
		palette: false,
		run: async (shell, { doctype, name, view }: OpenValue) => {
			await shell.router.push(routeFor(doctype, name, { view }));
		},
	};
}

function backItem(): ActItem<Shell> {
	return {
		name: "back",
		asks: ["confirm"],
		palette: false,
		run: ({ router }) => goBack(router),
	};
}

let leaving: Promise<{ path: string }> | null = null;

/** Goes to the page before this one in the tab; settles when the router has, so a discard confirm is waited on. */
function goBack(router: Router): Promise<{ path: string }> {
	if (router.options.history.state.back == null) throw new Error(__("No earlier page in this tab"));
	// `state.back` changes only when the pop lands: a second call before then would go back twice.
	leaving ??= arrive(router).finally(() => (leaving = null));
	return leaving;
}

function arrive(router: Router) {
	return new Promise<{ path: string }>((resolve, reject) => {
		const stop = () => {
			offAfter();
			offError();
		};
		const offAfter = router.afterEach((to, _from, failure) => {
			stop();
			if (!failure) return resolve({ path: to.fullPath });
			reject(
				new Error(
					isNavigationFailure(failure, NavigationFailureType.aborted)
						? __("The page did not change: the person kept their unsaved changes")
						: __("The page did not change: another navigation interrupted it")
				)
			);
		});
		// A guard that throws or a route that fails to load reports here, never to `afterEach`.
		const offError = router.onError((error) => {
			stop();
			reject(error);
		});
		router.back();
	});
}

function personItems(
	host: ShellActsHost,
	setColorScheme: (scheme: ColorScheme) => void
): ActItem<Shell>[] {
	return [
		{
			name: "my_settings",
			label: __("My settings"),
			icon: "lucide-circle-user",
			run: (shell) => shell.openSettings("desk", "profile"),
		},
		{
			name: "theme",
			asks: ["picker"],
			label: __("Theme"),
			icon: "lucide-sun-moon",
			argument: {
				label: __("Themes"),
				options: () => colorSchemes(),
			},
			run: (_shell, scheme: ColorScheme) => setColorScheme(scheme),
		},
		{
			name: "desk_v1",
			label: __("Desk v1"),
			icon: "lucide-arrow-left-right",
			run: () => leave("/app"),
		},
		{
			name: "log_out",
			asks: ["confirm"],
			label: __("Log out"),
			icon: "lucide-log-out",
			run: () => host.confirmLogout(),
		},
	];
}

function leave(href: string) {
	loadDocument(href);
}

// The menu closes on the click, so the confirmation is a toast.
export async function copyLink(link: string) {
	try {
		await navigator.clipboard.writeText(link);
	} catch {
		toast.error(__("Could not copy the link"));
		return;
	}
	toast.success(__("Link copied"));
}
