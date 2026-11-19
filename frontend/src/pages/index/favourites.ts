// The index's Favourites: boot's first 8, then the rest on "More", fetched once.
import { computed, ref } from "vue";
import { runMethod } from "@framework/ui/api";
import type { Boot } from "@/boot";

export type IndexFavourite = NonNullable<Boot["favourites"]>[number];

/** The More/Less chip's selection key; it keeps one key so the selection stays on it. */
export const MORE_FAVOURITES_KEY = "favourites:more";

/** The favourite's selection key, unique on the page. */
export function favouriteKey(favourite: IndexFavourite): string {
	const view = favourite.view ? `:${favourite.view}` : "";
	return `favourite:${favourite.doctype}:${favourite.name}${view}`;
}

export class Favourites {
	readonly open = ref(false);
	readonly loading = ref(false);
	private readonly rest = ref<IndexFavourite[] | null>(null);

	/** Boot's chips, then the fetched rest while open, less any boot already drew. */
	readonly shown = computed(() => {
		if (!this.open.value || !this.rest.value) return this.first;
		const drawn = new Set(this.first.map(favouriteKey));
		return [...this.first, ...this.rest.value.filter((chip) => !drawn.has(favouriteKey(chip)))];
	});

	constructor(
		private readonly first: IndexFavourite[],
		readonly hasMore: boolean
	) {}

	/** More opens the rest, fetching it the first time; Less goes back to boot's chips. */
	async toggle() {
		if (this.open.value) {
			this.open.value = false;
			return;
		}
		if (this.loading.value) return;

		if (!this.rest.value) {
			this.loading.value = true;
			try {
				this.rest.value = await fetchMore();
			} finally {
				this.loading.value = false;
			}
		}
		this.open.value = true;
	}
}

async function fetchMore(): Promise<IndexFavourite[]> {
	const response = await runMethod<IndexFavourite[]>(
		"frappe.shell.index_favourites.more_favourites",
		{},
		{ http: "GET" }
	);
	return response.data;
}
