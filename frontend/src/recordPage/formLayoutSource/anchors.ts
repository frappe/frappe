import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { InlineField, LayoutTree, LayoutTreeColumn, LayoutTreeSection, LayoutTreeTab } from "./types";

export interface Anchored {
	tree: LayoutTree;
	/** The unplaced fields no anchor took, in meta order. */
	rest: RawMetaField[];
}

/** Draws each unplaced custom field after its anchor field, or atop the container it names; a chain runs through `loose`. */
export function withAnchors(tree: LayoutTree, unplaced: RawMetaField[], loose: RawMetaField[]): Anchored {
	const anchors = new AnchorIndex(unplaced, loose);
	const anchored = tree.map((tab) => anchors.placeInTab(tab));
	return { tree: anchored, rest: unplaced.filter((field) => !anchors.taken.has(field.fieldname)) };
}

class AnchorIndex {
	readonly taken = new Set<string>();
	private followers = new Map<string, string[]>();
	private drawn: Set<string>;

	constructor(unplaced: RawMetaField[], loose: RawMetaField[]) {
		this.drawn = new Set(unplaced.map((field) => field.fieldname));
		for (const field of loose) {
			if (!field.insert_after) continue;
			const list = this.followers.get(field.insert_after) ?? [];
			list.push(field.fieldname);
			this.followers.set(field.insert_after, list);
		}
	}

	placeInTab(tab: LayoutTreeTab): LayoutTreeTab {
		const sections = tab.sections ?? [];
		const opener = sections.findIndex(hasColumn);
		const top = opener < 0 ? [] : this.follow(tab.name);
		return {
			...tab,
			sections: sections.map((section, index) =>
				this.placeInSection(section, index === opener ? top : [])
			),
		};
	}

	private placeInSection(section: LayoutTreeSection, above: string[]): LayoutTreeSection {
		const columns = section.columns ?? [];
		const top = columns.length ? [...above, ...this.follow(section.name)] : [];
		return {
			...section,
			columns: columns.map((column, index) => this.placeInColumn(column, index ? [] : top)),
		};
	}

	private placeInColumn(column: LayoutTreeColumn, above: string[]): LayoutTreeColumn {
		const top = [...above, ...this.follow(column.name)];
		const fields = (column.fields ?? []).flatMap((entry) => [entry, ...this.follow(fieldnameOf(entry))]);
		return { ...column, fields: [...top, ...fields] };
	}

	/** The drawn fields anchored to `name`, depth first in meta order; a name the tree lists twice draws them once. */
	private follow(name: string | undefined): string[] {
		if (!name) return [];
		return (this.followers.get(name) ?? []).flatMap((fieldname) => {
			if (this.taken.has(fieldname)) return [];
			this.taken.add(fieldname);
			const chain = this.follow(fieldname);
			return this.drawn.has(fieldname) ? [fieldname, ...chain] : chain;
		});
	}
}

function hasColumn(section: LayoutTreeSection): boolean {
	return Boolean(section.columns?.length);
}

function fieldnameOf(entry: string | InlineField): string {
	return typeof entry === "string" ? entry : entry.fieldname;
}
