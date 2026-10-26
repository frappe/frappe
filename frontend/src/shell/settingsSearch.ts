// Settings search over the pane list and the label index the server sent with it; no request per query.
import { __ } from "@/i18n";
import { matchTier } from "./matchTier";
import type { SettingsAddressBook } from "./settingsAddress";
import type { PanesReply, SettingsIndexEntry, SettingsPane } from "./settingsPanes";

/** One result: a pane, a block, a field or a setting a component block declared. */
export interface SettingsHit {
	prefix: string;
	pane: SettingsPane;
	block?: string;
	fieldname?: string;
	label: string;
	/** Where it lives: the pane and block, led by the app's title for another app's result. */
	where: string;
}

export interface SettingsResults {
	/** Matches in the framework's panes and the current app's. */
	own: SettingsHit[];
	/** Matches in every other app. */
	other: SettingsHit[];
}

const LIMIT = 30;

interface Entry {
	prefix: string;
	pane: SettingsPane;
	block?: string;
	blockLabel?: string;
	fieldname?: string;
	label: string;
	description?: string;
	keywords?: string[];
}

export class SettingsSearch {
	private readonly entries: Entry[] = [];

	constructor(
		private readonly reply: PanesReply,
		private readonly book: SettingsAddressBook
	) {
		const indexed = new Map<string, SettingsIndexEntry[]>();
		for (const entry of reply.index) {
			const key = `${entry.app}/${entry.pane}`;
			indexed.set(key, [...(indexed.get(key) ?? []), entry]);
		}
		for (const { prefix, panes } of book.everyGroup()) {
			for (const pane of panes) this.addPane(prefix, pane, indexed.get(`${pane.app}/${pane.key}`) ?? []);
		}
	}

	/** Each list ranked by how well the label matches, then in pane-list order. */
	find(query: string): SettingsResults {
		const needle = query.trim().toLowerCase();
		const results: SettingsResults = { own: [], other: [] };
		if (!needle) return results;

		const ranked = this.entries
			.map((entry) => ({ entry, rank: rank(entry, needle) }))
			.filter((match): match is { entry: Entry; rank: number } => match.rank !== null)
			.sort((one, other) => one.rank - other.rank);
		for (const { entry } of ranked) {
			const list = this.book.isForeign(entry.prefix) ? results.other : results.own;
			if (list.length < LIMIT) list.push(this.hit(entry));
		}
		return results;
	}

	private addPane(prefix: string, pane: SettingsPane, indexed: SettingsIndexEntry[]) {
		this.entries.push({ prefix, pane, label: pane.label, description: pane.description });
		for (const block of pane.blocks) {
			if (!block.label) continue;
			this.entries.push({
				prefix,
				pane,
				block: block.key,
				label: block.label,
				description: block.description,
			});
		}
		for (const { block, label, fieldname, description, keywords } of indexed) {
			const shown = label || fieldname;
			if (!shown) continue;
			const blockLabel = pane.blocks.find((one) => one.key === block)?.label;
			this.entries.push({ prefix, pane, block, blockLabel, fieldname, label: shown, description, keywords });
		}
	}

	private hit({ prefix, pane, block, blockLabel, fieldname, label }: Entry): SettingsHit {
		const path = [block ? pane.label : undefined, blockLabel].filter(Boolean).map((one) => __(one!));
		const app = this.reply.titles[pane.app];
		const where = this.book.isForeign(prefix) || !path.length ? [app, ...path] : path;
		return { prefix, pane, block, fieldname, label: __(label), where: where.join(" › ") };
	}
}

/** 0 when the label starts with the query, 1 when a word in it does, 2 anywhere in it, 3 in its other text. */
function rank(entry: Entry, needle: string): number | null {
	const tier = matchTier(__(entry.label), needle);
	if (tier !== null) return tier;
	const other = [entry.description, ...(entry.keywords ?? [])];
	return other.some((text) => text && __(text).toLowerCase().includes(needle)) ? 3 : null;
}
