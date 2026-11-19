// The settings address, `#settings/<prefix>/<pane>/<block>`: what it shows and which groups list.
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import type { PanesReply, SettingsBlock, SettingsPane } from "./settingsPanes";

/** The framework's app, whose panes list on top with no heading. */
export const FRAMEWORK = "frappe";

/** A pane in the sidebar, under its home address `prefix/pane`. */
export interface ShownPane {
	address: string;
	prefix: string;
	/** Its blocks are the sidebar's list for it, placements included. */
	pane: SettingsPane;
	/** The home address of each of `pane.blocks`. */
	blocks: string[];
}

export interface PaneGroup {
	key: string;
	label?: string;
	panes: ShownPane[];
}

export type Resolution =
	| {
			prefix: string;
			pane: SettingsPane;
			/** A block of the pane to scroll to; an unknown one is left out. */
			block?: string;
			/** The full address a short one, or a block's home address, is replaced by. */
			rewrite?: string[];
			/** The pane is drawn from its home, not from the sidebar, for this visit. */
			home?: boolean;
	  }
	| { refused: true };

/** One user's panes and the sidebar of the prefix the desk is open on. */
export class SettingsAddressBook {
	readonly currentPrefix: string;
	private readonly frameworkPrefix: string;
	private readonly homes = new Map<string, ShownPane>();
	private readonly byPrefix = new Map<string, string[]>();
	private readonly blocks = new Map<string, SettingsBlock>();
	private readonly placed = new Map<string, ShownPane>();
	private readonly firstPlaces = new Map<string, ShownPane>();
	private readonly groupsOfSidebar: { label?: string; panes: ShownPane[] }[] = [];

	constructor(
		private readonly reply: PanesReply,
		boot: Pick<Boot, "prefixes" | "app">
	) {
		const prefixOf = new Map(
			Object.entries(boot.prefixes).map(([prefix, { app }]) => [app, prefix])
		);
		for (const pane of reply.panes) this.addHome(pane, prefixOf.get(pane.app));
		this.frameworkPrefix = prefixOf.get(FRAMEWORK)!;
		const open = boot.app ? prefixOf.get(boot.app) : undefined;
		this.currentPrefix = open && reply.sidebars[open] ? open : this.frameworkPrefix;
		this.placeSidebar(reply.sidebars[this.currentPrefix]?.groups ?? []);
	}

	/** The sidebar's groups, then a visited prefix's panes the sidebar does not place; `home` is drawn from its home. */
	groups(visiting?: string, home?: string): PaneGroup[] {
		const drawn = this.groupsOfSidebar.map(({ label, panes }, index) => ({
			key: String(index),
			label,
			panes: panes.map((shown) => (shown.address === home ? this.homes.get(home)! : shown)),
		}));
		const left = (visiting ? this.byPrefix.get(visiting) ?? [] : [])
			.filter((address) => !this.placed.has(address))
			.map((address) => this.homes.get(address)!);
		if (!left.length) return drawn;
		return [...drawn, { key: `visiting:${visiting}`, label: this.titleOf(left[0].pane), panes: left }];
	}

	/** Every pane at its home, grouped by prefix, for the palette and search. */
	everyPane(): ShownPane[] {
		return [...this.byPrefix.values()].flat().map((address) => this.homes.get(address)!);
	}

	/** The panes the sidebar lists, in its order. */
	sidebarPanes(): ShownPane[] {
		return this.groupsOfSidebar.flatMap((group) => group.panes);
	}

	/** The first sidebar pane that holds the block, by its home address. */
	placeOf(blockAddress: string): ShownPane | undefined {
		return this.firstPlaces.get(blockAddress);
	}

	isPlaced(paneAddress: string): boolean {
		return this.placed.has(paneAddress);
	}

	/** `home` is a pane address to show from its home, as a search pick of a block with no place asks. */
	resolve(segments: string[], home?: string): Resolution {
		const [prefix = this.currentPrefix, paneKey, block, ...rest] = withoutTrailingEmpty(segments);
		if (rest.length) return { refused: true };

		if (!paneKey) {
			const first = this.firstPaneOf(prefix);
			if (!first) return { refused: true };
			return { ...this.show(first), rewrite: [first.prefix, first.pane.key] };
		}
		if (!this.byPrefix.has(prefix)) return { refused: true };

		const address = `${prefix}/${paneKey}`;
		const atHome = this.homes.get(address);
		if (!atHome) return { refused: true };
		const placed = address === home ? undefined : this.placed.get(address);
		if (!block) return this.show(placed ?? atHome);

		if (atHome.pane.blocks.some((candidate) => candidate.key === block)) {
			const blockAddress = `${address}/${block}`;
			if (address === home) return { ...this.show(atHome), block };
			if (placed?.blocks.includes(blockAddress)) return { ...this.show(placed), block };
			const place = this.firstPlaces.get(blockAddress);
			if (!place) return { ...this.show(atHome), block };
			return { ...this.show(place), block, rewrite: [place.prefix, place.pane.key, block] };
		}
		if (!placed) return this.show(atHome);
		const known = placed.pane.blocks.some((candidate) => candidate.key === block);
		return known ? { ...this.show(placed), block } : this.show(placed);
	}

	private show(shown: ShownPane): Resolution {
		const { prefix, pane } = shown;
		return this.placed.get(shown.address) === shown ? { prefix, pane } : { prefix, pane, home: true };
	}

	/** The prefix's first pane in sidebar order; with none placed, its first pane at home; for the desk's own prefix with no pane at all, the sidebar's first. */
	private firstPaneOf(prefix: string): ShownPane | undefined {
		const sidebar = this.sidebarPanes();
		const first = sidebar.find((shown) => shown.prefix === prefix) ?? this.homes.get(this.byPrefix.get(prefix)?.[0] ?? "");
		return first ?? (prefix === this.currentPrefix ? sidebar[0] : undefined);
	}

	private titleOf(pane: SettingsPane): string {
		return this.reply.titles[pane.app];
	}

	private addHome(pane: SettingsPane, prefix?: string) {
		if (!prefix) return;
		const address = `${prefix}/${pane.key}`;
		const blocks = pane.blocks.map((block) => `${address}/${block.key}`);
		blocks.forEach((blockAddress, index) => this.blocks.set(blockAddress, pane.blocks[index]));
		this.homes.set(address, { address, prefix, pane, blocks });
		this.byPrefix.set(prefix, [...(this.byPrefix.get(prefix) ?? []), address]);
	}

	private placeSidebar(groups: PanesReply["sidebars"][string]["groups"]) {
		for (const group of groups) {
			const panes = group.panes.flatMap((entry) => this.place(entry.pane, entry.blocks) ?? []);
			if (!panes.length) continue;
			const label = group.label ? __(group.label) : group.app ? this.reply.titles[group.app] : undefined;
			this.groupsOfSidebar.push({ label, panes });
		}
	}

	private place(address: string, blocks: string[]): ShownPane | undefined {
		const home = this.homes.get(address);
		if (!home) return;
		const known = blocks.filter((block) => this.blocks.has(block));
		const same = known.length === home.blocks.length && known.every((block, index) => block === home.blocks[index]);
		const pane = same ? home.pane : { ...home.pane, blocks: known.map((block) => this.blocks.get(block)!) };
		const shown = { address, prefix: home.prefix, pane, blocks: known };
		this.placed.set(address, shown);
		for (const block of known) if (!this.firstPlaces.has(block)) this.firstPlaces.set(block, shown);
		return shown;
	}
}

/** `#settings/` and `#settings/desk/` are the short addresses they look like. */
function withoutTrailingEmpty(segments: string[]): string[] {
	const end = segments.findLastIndex((segment) => segment !== "");
	return segments.slice(0, end + 1);
}
