// The sidebars the server resolves for an app that ships no arrangement, for the settings tests.
import type { PanesReply, SettingsPane, SidebarGroup } from "../../settingsPanes";

/** Each app's prefix (the apps' panes come with), as the boot's `prefixes` names them. */
export function defaultSidebars(panes: SettingsPane[], prefixes: Record<string, string>): PanesReply["sidebars"] {
	const entries = (app: string): SidebarGroup["panes"] =>
		panes
			.filter((pane) => pane.app === app)
			.map((pane) => ({
				pane: `${prefixes[app]}/${pane.key}`,
				blocks: pane.blocks.map((block) => `${prefixes[app]}/${pane.key}/${block.key}`),
			}));

	const sidebars: PanesReply["sidebars"] = {};
	for (const app of new Set(panes.map((pane) => pane.app))) {
		const groups: SidebarGroup[] = [{ panes: entries("frappe") }];
		if (app !== "frappe") groups.push({ app, panes: entries(app) });
		sidebars[prefixes[app]] = { groups: groups.filter((group) => group.panes.length) };
	}
	return sidebars;
}
