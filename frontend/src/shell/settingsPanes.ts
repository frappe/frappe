// The settings dialog's pane list: read on first open and held for the tab.
import { runMethod } from "@framework/ui/api";
import type { Boot } from "@/boot";

export type SaveMode = "auto" | "button";

export interface SettingsBinding {
	type: "Single" | "Record";
	doctype: string;
	resolver?: "session_user";
}

export interface SettingsBlock {
	key: string;
	/** The app that ships the block, which differs from its pane's app for a foreign block. */
	app: string;
	save_mode: SaveMode;
	label?: string;
	description?: string;
	binding?: SettingsBinding;
	/** A generated block's fields (none: the doctype's whole layout), or the fields a bound component saves. */
	fields?: string[];
	left_out_fields?: string[];
	read_only_fields?: string[];
	read_only?: boolean;
	component?: string;
	bindings?: Record<string, SettingsBinding>;
}

export interface SettingsPane {
	app: string;
	key: string;
	label: string;
	icon?: string;
	description?: string;
	blocks: SettingsBlock[];
}

export interface SettingsIndexEntry {
	app: string;
	pane: string;
	block: string;
	fieldname?: string;
	/** Left out when blank: a field's row is then titled by its fieldname; an imported component setting has none. */
	label?: string;
	description?: string;
	keywords?: string[];
}

/** A pane in a sidebar group: its home address `prefix/pane`, and the addresses `prefix/pane/block` of the blocks it shows. */
export interface SidebarPane {
	pane: string;
	blocks: string[];
}

export interface SidebarGroup {
	/** Left out for the first group, and for an app's default group, which the app's title heads. */
	label?: string;
	app?: string;
	panes: SidebarPane[];
}

export interface PanesReply {
	panes: SettingsPane[];
	/** The sidebar each prefix's desk draws, after the permission filter; a prefix the user sees nothing in has none. */
	sidebars: Record<string, { groups: SidebarGroup[] }>;
	index: SettingsIndexEntry[];
	/** Each app's title, for the apps the panes come from. */
	titles: Record<string, string>;
}

const held = new Map<string, Promise<PanesReply>>();

/** The panes this user may see, fetched once per `metadata_version` and user; a failed read is not kept. */
export function fetchPanes(boot: Boot): Promise<PanesReply> {
	const key = `${boot.metadata_version}:${boot.session.user.name}`;
	let reply = held.get(key);
	if (!reply) {
		reply = runMethod<PanesReply>("frappe.shell.settings.get_panes", {}, { http: "GET" }).then(
			(envelope) => envelope.data
		);
		reply.catch(() => held.delete(key));
		held.set(key, reply);
	}
	return reply;
}
