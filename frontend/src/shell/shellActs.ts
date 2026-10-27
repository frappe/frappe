// The shell surface, `shell`: the acts that outlive a page. The rail's app menu, the avatar menu
// and the sidebar's edge draw from it, so each entry is declared once.
import { onScopeDispose } from "vue";
import type { Router } from "vue-router";
import { toast, useColorScheme, type ColorScheme } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { acts, type ActItem, type AvailableAct } from "@/acts/dispatcher";
import { doctypeRight } from "@/acts/doctypeRight";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { useAppActs } from "./appActs";
import { openCreate, type CreatedDoc, type CreateOptions } from "./create";

/** Opens `#settings/<prefix>/<pane>/<block>`; each segment is optional, in order. */
export type OpenSettings = (prefix?: string, pane?: string, block?: string) => void;

/** What a shell act's `run` receives. Nothing in it needs a record. */
export interface Shell {
	router: Router;
	toast: { success: (message: string) => void; error: (message: string) => void };
	call: (method: string, params?: Record<string, any>) => Promise<any>;
	run: (name: string, value?: unknown) => Promise<unknown>;
	create: (doctype: string, options?: CreateOptions) => Promise<CreatedDoc | null>;
	openSettings: OpenSettings;
}

/** `shell.create`'s value: a doctype, or a doctype with the values its record starts with. */
type CreateValue = string | { doctype: string; values?: Record<string, any> };

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
	const shell = shellFor(host);
	const appActs = useAppActs();
	const { setColorScheme } = useColorScheme();
	const release = acts.register({
		surfaces: {
			shell: () =>
				[...shellItems(host, setColorScheme), ...appActs.items()].map((item) => ({
					item,
					hidden: false,
				})),
		},
		context: () => shell,
		passes: (right) => typeof right !== "string" && doctypeRight.passes(right),
		settled: (right) => (typeof right === "string" ? undefined : doctypeRight.settled(right)),
		loading: (name) => (isAppAct(name) ? appActs.pending() : undefined),
		hold: async (work) => work(),
		failed: (error) => void toast.error(error instanceof Error ? error.message : String(error)),
	});
	onScopeDispose(release);
	return { appActsPending: appActs.pending };
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

function shellFor(host: ShellActsHost): Shell {
	return {
		router: host.router,
		toast: {
			success: (message) => toast.success(message),
			error: (message) => toast.error(message),
		},
		call: (method, params) => runMethod(method, params).then((envelope) => envelope.data),
		run: (name, value) => acts.run(name, value),
		create: (doctype, options) => openCreate(doctype, options),
		openSettings: host.openSettings,
	};
}

function shellItems(
	host: ShellActsHost,
	setColorScheme: (scheme: ColorScheme) => void
): ActItem<Shell>[] {
	return [
		...(host.rail ? railItems(host.rail) : []),
		openSettingsItem(),
		...personItems(host, setColorScheme),
		createItem(),
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
			label: __("Customize sidebar"),
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
			icon: collapsed ? "lucide-panel-left-open" : "lucide-panel-left-close",
			run: () => rail.toggleSidebar(),
		});
	return items;
}

function openSettingsItem(): ActItem<Shell> {
	return {
		name: "open_settings",
		label: __("Settings"),
		icon: "lucide-settings",
		run: (shell, address?: SettingsAddress) => shell.openSettings(...segmentsOf(address)),
	};
}

/** The address's segments in order, with no empty ones after the last given. */
function segmentsOf({ prefix, pane, block }: SettingsAddress = {}) {
	const segments = [prefix, pane, block];
	while (segments.length && segments[segments.length - 1] === undefined) segments.pop();
	return segments;
}

// A palette row has no doctype to give Create.
function createItem(): ActItem<Shell> {
	return {
		name: "create",
		label: __("Create"),
		icon: "lucide-plus",
		palette: false,
		run: (shell, value: CreateValue) => {
			const { doctype, values } =
				typeof value === "string" ? { doctype: value, values: undefined } : value ?? {};
			if (!doctype) throw new Error(__("Create needs a doctype"));
			return shell.create(doctype, { values });
		},
	};
}

function personItems(
	host: ShellActsHost,
	setColorScheme: (scheme: ColorScheme) => void
): ActItem<Shell>[] {
	const user = host.boot.session.user.name;
	return [
		{
			// Workaround: the settings dialog has no profile pane yet, so this opens v1's User form.
			name: "my_settings",
			label: __("My settings"),
			icon: "lucide-circle-user",
			run: () => leave(`/app/user/${encodeURIComponent(user)}`),
		},
		{
			name: "theme",
			label: __("Theme"),
			icon: "lucide-sun-moon",
			argument: {
				label: __("Theme"),
				options: () => colorSchemes().map(({ value, label }) => ({ value, label })),
			},
			run: (_shell, scheme: ColorScheme) => {
				if (!colorSchemes().some(({ value }) => value === scheme))
					throw new Error(__("Theme is light, dark or system"));
				setColorScheme(scheme);
			},
		},
		{
			name: "desk_v1",
			label: __("Desk v1"),
			icon: "lucide-arrow-left-right",
			run: () => leave("/app"),
		},
		{
			name: "log_out",
			label: __("Log out"),
			icon: "lucide-log-out",
			run: () => host.confirmLogout(),
		},
	];
}

function leave(href: string) {
	window.location.assign(href);
}

// The menu closes on the click, so the confirmation is a toast.
async function copyLink(link: string) {
	try {
		await navigator.clipboard.writeText(link);
	} catch {
		toast.error(__("Could not copy the link"));
		return;
	}
	toast.success(__("Link copied"));
}
