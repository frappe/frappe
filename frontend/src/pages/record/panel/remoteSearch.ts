// Options matched on the server as the reader types, for the assign, share and tag pickers.
import { computed, ref, type Ref } from "vue";
import { useDebounceFn } from "@vueuse/core";
import { listDocuments, searchDocuments } from "@framework/ui/api";
import { errorMessage } from "@/recordPage";
import { seedTagColors } from "@/tagColors";

export type SearchOption = { label: string; value: string; image?: string };

const PAGE_LENGTH = 10;
// A dict, not a list: the server hands User searches to a standard query that reads filters by key.
const USER_FILTERS = {
	enabled: 1,
	user_type: "System User",
	name: ["not in", ["Administrator", "Guest"]],
};

export function useUserSearch(pinned: Ref<SearchOption[]>) {
	return useRemoteSearch(searchUsers, pinned);
}

export function useTagSearch(pinned: Ref<SearchOption[]>) {
	return useRemoteSearch(searchTags, pinned);
}

/** The server's answer with the pinned options filling its gaps; a stale answer is dropped. */
export function useRemoteSearch<Option extends SearchOption>(
	fetchOptions: (query: string) => Promise<Option[]>,
	pinned: Ref<Option[]>
) {
	const results = ref<Option[]>([]) as Ref<Option[]>;
	const loading = ref(false);
	const error = ref("");
	const searched = ref(false);

	let latestRequest = 0;

	async function search(query = "") {
		const request = ++latestRequest;
		loading.value = true;
		try {
			const found = await fetchOptions(query);
			if (request !== latestRequest) return;
			results.value = found;
			error.value = "";
			searched.value = true;
		} catch (caught) {
			if (request !== latestRequest) return;
			error.value = errorMessage(caught);
		} finally {
			if (request === latestRequest) loading.value = false;
		}
	}

	const searchSoon = useDebounceFn(search, 250);

	// The server's order wins, so picking a pinned option never reorders the list under the pointer.
	const options = computed(() => {
		const shown = new Map(results.value.map((option) => [option.value, option]));
		for (const option of pinned.value) if (!shown.has(option.value)) shown.set(option.value, option);
		return [...shown.values()];
	});

	return { options, loading, error, searched, search, searchSoon };
}

async function searchUsers(query: string): Promise<SearchOption[]> {
	const rows = await findUsers(query);
	return rows.map((row) => ({ label: row.label || row.value, value: row.value }));
}

/** The link search's users: each one's id as `value`, and the full name as `description`. */
export async function findUsers(query: string) {
	const { data } = await searchDocuments("User", {
		txt: query,
		filters: USER_FILTERS,
		limit: PAGE_LENGTH,
	});
	return data;
}

async function searchTags(query: string): Promise<SearchOption[]> {
	const text = query.trim();
	const { data } = await listDocuments<{ name: string; color?: string | null }>("Tag", {
		fields: ["name", "color"],
		filters: text ? [["name", "like", `%${text}%`]] : [],
		order_by: "name asc",
		limit: PAGE_LENGTH,
	});
	seedTagColors(Object.fromEntries(data.map((tag) => [tag.name, tag.color])));
	return data.map((tag) => ({ label: tag.name, value: tag.name }));
}
