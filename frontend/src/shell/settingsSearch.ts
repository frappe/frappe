// Settings search over the pane list and the label index the server sent with it; no request per query.
import { __ } from "@/i18n";
import { matchTier } from "./matchTier";
import type { SettingsAddressBook, ShownPane } from "./settingsAddress";
import type { PanesReply, SettingsBlock, SettingsIndexEntry, SettingsPane } from "./settingsPanes";

/** One result: a pane, a block, a field or a setting a component block declared. */
export interface SettingsHit {
	/** Unique in its search index, so it keys the result row. */
	id: number;
	prefix: string;
	pane: SettingsPane;
	block?: string;
	fieldname?: string;
	label: string;
	/** Where it lives: the pane and block, led by the app's title for another app's result. */
	where: string;
	/** It has no place in the sidebar: the pane opens from its home for the visit. */
	home?: boolean;
}

export interface SettingsResults {
	/** Matches in a block or pane the sidebar places, at its first place. */
	own: SettingsHit[];
	/** Matches in a hidden or unplaced pane or block, and in other apps' panes. */
	elsewhere: SettingsHit[];
}

const LIMIT = 30;

interface PlacedBlock {
	/** The block's home address. */
	address: string;
	block: SettingsBlock;
}

interface Entry {
	id: number;
	prefix: string;
	pane: SettingsPane;
	block?: string;
	blockLabel?: string;
	fieldname?: string;
	label: string;
	description?: string;
	keywords?: string[];
	home?: boolean;
}

export class SettingsSearch {
	private readonly entries: Entry[] = [];
	private readonly indexed = new Map<string, SettingsIndexEntry[]>();

	constructor(
		private readonly reply: PanesReply,
		private readonly book: SettingsAddressBook
	) {
		const addressOf = new Map(book.everyPane().map(({ address, pane }) => [`${pane.app}/${pane.key}`, address]));
		for (const entry of reply.index) {
			const address = `${addressOf.get(`${entry.app}/${entry.pane}`)}/${entry.block}`;
			this.indexed.set(address, [...(this.indexed.get(address) ?? []), entry]);
		}
		for (const shown of book.sidebarPanes()) {
			const here = shown.blocks.map((address, index) => ({ address, block: shown.pane.blocks[index] }));
			this.addPane(shown, here.filter(({ address }) => book.placeOf(address)?.address === shown.address));
		}
		for (const shown of book.everyPane()) {
			const unplaced = shown.blocks.map((address, index) => ({ address, block: shown.pane.blocks[index] }));
			const left = unplaced.filter(({ address }) => !book.placeOf(address));
			if (!book.isPlaced(shown.address)) this.addPane(shown, left, true);
			else if (left.length) this.addBlocks(shown, left, true);
		}
	}

	/** Each list ranked by how well the label matches, then in pane-list order. */
	find(query: string): SettingsResults {
		const needle = query.trim().toLowerCase();
		const results: SettingsResults = { own: [], elsewhere: [] };
		if (!needle) return results;

		const ranked = this.entries
			.map((entry) => ({ entry, rank: rank(entry, needle) }))
			.filter((match): match is { entry: Entry; rank: number } => match.rank !== null)
			.sort((one, other) => one.rank - other.rank);
		for (const { entry } of ranked) {
			const list = entry.home ? results.elsewhere : results.own;
			if (list.length < LIMIT) list.push(this.hit(entry));
		}
		return results;
	}

	/** The pane's own row, then its `blocks`; `home` rows open the pane from its home. */
	private addPane(shown: ShownPane, blocks: PlacedBlock[], home?: boolean) {
		const { prefix, pane } = shown;
		this.add({ prefix, pane, label: pane.label, description: pane.description, home });
		this.addBlocks(shown, blocks, home);
	}

	private addBlocks({ prefix, pane }: ShownPane, blocks: PlacedBlock[], home?: boolean) {
		const entries = new Map<string, Entry>();
		for (const { address, block } of blocks) {
			if (!block.label) continue;
			entries.set(address, this.add({ prefix, pane, block: block.key, label: block.label, description: block.description, home }));
		}
		for (const { address, block } of blocks) {
			for (const { label, fieldname, description, keywords } of this.indexed.get(address) ?? []) {
				const shown = label || fieldname;
				if (!shown) continue;
				const blockEntry = entries.get(address);
				// A setting named as its block is the block itself: two rows would share a label.
				if (!fieldname && blockEntry?.label === shown) {
					blockEntry.keywords = [...new Set([...(blockEntry.keywords ?? []), ...(keywords ?? [])])];
					continue;
				}
				const blockLabel = blockEntry?.label;
				this.add({ prefix, pane, block: block.key, blockLabel, fieldname, label: shown, description, keywords, home });
			}
		}
	}

	private add(entry: Omit<Entry, "id">): Entry {
		const added = { ...entry, id: this.entries.length };
		this.entries.push(added);
		return added;
	}

	private hit({ id, prefix, pane, block, blockLabel, fieldname, label, home }: Entry): SettingsHit {
		const path = [block ? pane.label : undefined, blockLabel].filter(Boolean).map((one) => __(one!));
		const app = this.reply.titles[pane.app];
		const where = (home && prefix !== this.book.currentPrefix) || !path.length ? [app, ...path] : path;
		return { id, prefix, pane, block, fieldname, label: __(label), where: where.join(" › "), home };
	}
}

/** 0 when the label starts with the query, 1 when a word in it does, 2 anywhere in it, 3 in its other text. */
function rank(entry: Entry, needle: string): number | null {
	const tier = matchTier(__(entry.label), needle);
	if (tier !== null) return tier;
	const other = [entry.description, ...(entry.keywords ?? [])];
	return other.some((text) => text && __(text).toLowerCase().includes(needle)) ? 3 : null;
}
