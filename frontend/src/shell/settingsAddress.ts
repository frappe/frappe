// The settings address, `#settings/<prefix>/<pane>/<block>`: what it shows and which groups list.
import type { Boot } from "@/boot";
import type { PanesReply, SettingsPane } from "./settingsPanes";

/** The framework's app, whose panes list on top with no heading. */
export const FRAMEWORK = "frappe";

export interface PaneGroup {
	prefix: string;
	/** The app's title; none for the framework's group. */
	label?: string;
	panes: SettingsPane[];
}

export type Resolution =
	| {
			prefix: string;
			pane: SettingsPane;
			/** A block of the pane to scroll to; an unknown one is left out. */
			block?: string;
			/** The full address a short one is replaced by. */
			rewrite?: string[];
	  }
	| { refused: true };

/** One user's panes, grouped by prefix, as seen from the prefix the desk is open on. */
export class SettingsAddressBook {
	private readonly byPrefix = new Map<string, SettingsPane[]>();
	private readonly frameworkPrefix: string;
	private readonly currentPrefix: string;

	constructor(
		private readonly reply: PanesReply,
		boot: Pick<Boot, "prefixes" | "app">
	) {
		const prefixOf = new Map(
			Object.entries(boot.prefixes).map(([prefix, { app }]) => [app, prefix])
		);
		for (const pane of reply.panes) {
			const prefix = prefixOf.get(pane.app);
			if (!prefix) continue;
			this.byPrefix.set(prefix, [...(this.byPrefix.get(prefix) ?? []), pane]);
		}
		this.frameworkPrefix = prefixOf.get(FRAMEWORK)!;
		const open = boot.app ? prefixOf.get(boot.app) : undefined;
		this.currentPrefix = open && this.byPrefix.has(open) ? open : this.frameworkPrefix;
	}

	/** The framework's panes, the current app's group, and a visited foreign app's group. */
	groups(visiting?: string): PaneGroup[] {
		const prefixes = [this.frameworkPrefix, this.currentPrefix, visiting];
		return [...new Set(prefixes)]
			.filter((prefix): prefix is string => !!prefix && this.byPrefix.has(prefix))
			.map((prefix) => this.group(prefix));
	}

	/** Whether a shown prefix is one `groups()` lists only while it is visited. */
	isForeign(prefix: string): boolean {
		return prefix !== this.frameworkPrefix && prefix !== this.currentPrefix;
	}

	resolve(segments: string[]): Resolution {
		const [prefix = this.currentPrefix, paneKey, block, ...rest] = withoutTrailingEmpty(segments);
		const panes = this.byPrefix.get(prefix);
		if (!panes || rest.length) return { refused: true };

		if (!paneKey) return { prefix, pane: panes[0], rewrite: [prefix, panes[0].key] };

		const pane = panes.find((candidate) => candidate.key === paneKey);
		if (!pane) return { refused: true };

		const known = pane.blocks.some((candidate) => candidate.key === block);
		return known ? { prefix, pane, block } : { prefix, pane };
	}

	private group(prefix: string): PaneGroup {
		const panes = this.byPrefix.get(prefix)!;
		const label = prefix === this.frameworkPrefix ? undefined : this.reply.titles[panes[0].app];
		return { prefix, label, panes };
	}
}

/** `#settings/` and `#settings/desk/` are the short addresses they look like. */
function withoutTrailingEmpty(segments: string[]): string[] {
	const end = segments.findLastIndex((segment) => segment !== "");
	return segments.slice(0, end + 1);
}
