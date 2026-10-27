// The arrow-key selection on the index: one movement over every section's items, in page order.
import { computed, ref, type ComputedRef, type Ref } from "vue";

/** One item the arrow keys can reach. `key` is unique on the page; Enter calls `run`, else opens `href`. */
export type Selectable = { key: string; href?: string; run?: () => unknown };

/** A run of items drawn in `columns` columns, in reading order. A list is one column. */
export type SelectionSection = { items: Selectable[]; columns: number };

type Place = { section: number; index: number };

const ARROWS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]);

/** The element id an item draws with, so the filter box can point at the selected one. */
export function selectableId(key: string): string {
	// Every other character as its code point, `_` too, so two record names never share an id.
	return `index-item-${key.replace(/[^A-Za-z0-9-]/gu, (c) => `_${c.codePointAt(0)!.toString(16)}_`)}`;
}

export class Selection {
	readonly selected: Ref<string | null> = ref(null);
	private readonly sections: ComputedRef<SelectionSection[]>;

	constructor(sections: () => SelectionSection[]) {
		this.sections = computed(() => sections().filter((section) => section.items.length));
	}

	isSelected(key: string): boolean {
		return this.selected.value === key;
	}

	/** `selectableId`, for the results chunk: importing it there splits this module out of the page's chunk. */
	idOf(key: string): string {
		return selectableId(key);
	}

	/** The selected item's element id, for `aria-activedescendant`. */
	activeId(): string | undefined {
		return this.selected.value ? selectableId(this.selected.value) : undefined;
	}

	/** The selected item, else the first: what Enter opens. */
	target(): Selectable | undefined {
		const place = this.place();
		return place ? this.itemAt(place) : this.sections.value[0]?.items[0];
	}

	selectFirst() {
		this.selected.value = this.sections.value[0]?.items[0]?.key ?? null;
	}

	/** Selects the first item when the selected one is no longer drawn, as when rows arrive late. */
	keep() {
		if (!this.place()) this.selectFirst();
	}

	clear() {
		this.selected.value = null;
	}

	/** Moves for an arrow key; false for any other key. */
	move(key: string): boolean {
		if (!ARROWS.has(key)) return false;
		const from = this.place();
		const to = from ? this.step(from, key) : { section: 0, index: 0 };
		const item = this.itemAt(to);
		if (item) this.selected.value = item.key;
		return true;
	}

	private step(from: Place, key: string): Place {
		const { items, columns } = this.sections.value[from.section];
		const row = Math.floor(from.index / columns);
		const lastRow = Math.floor((items.length - 1) / columns);

		switch (key) {
			case "ArrowRight":
				return from.index + 1 < items.length ? { ...from, index: from.index + 1 } : this.next(from);
			case "ArrowLeft":
				return from.index > 0 ? { ...from, index: from.index - 1 } : this.previous(from);
			case "ArrowDown":
				return row < lastRow
					? { ...from, index: Math.min(from.index + columns, items.length - 1) }
					: this.next(from);
			default:
				return row > 0 ? { ...from, index: from.index - columns } : this.previous(from);
		}
	}

	/** The next section's first item; the last item stays put. */
	private next(from: Place): Place {
		return from.section + 1 < this.sections.value.length
			? { section: from.section + 1, index: 0 }
			: from;
	}

	/** The previous section's last item; the first item stays put. */
	private previous(from: Place): Place {
		const before = this.sections.value[from.section - 1];
		return before ? { section: from.section - 1, index: before.items.length - 1 } : from;
	}

	private place(): Place | null {
		const sections = this.sections.value;
		for (let section = 0; section < sections.length; section++) {
			const index = sections[section].items.findIndex(
				(item) => item.key === this.selected.value
			);
			if (index !== -1) return { section, index };
		}
		return null;
	}

	private itemAt(place: Place): Selectable | undefined {
		return this.sections.value[place.section]?.items[place.index];
	}
}
