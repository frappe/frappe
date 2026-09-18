// Options matched on the server as the reader types, for the assign, share and tag pickers.
import { computed, ref, type Ref } from "vue";
import { useDebounceFn } from "@vueuse/core";
import { searchDocuments } from "@framework/ui/api";
import { errorMessage } from "@/recordPage";

export type SearchOption = { label: string; value: string; image?: string };

type Call = (method: string, params?: Record<string, any>) => Promise<any>;

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

export function useTagSearch(call: Call, doctype: string, pinned: Ref<SearchOption[]>) {
	return useRemoteSearch((query) => searchTags(call, doctype, query), pinned);
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
	const { data } = await searchDocuments("User", {
		txt: query,
		filters: USER_FILTERS,
		limit: PAGE_LENGTH,
	});
	return data.map((row) => ({ label: row.label || row.value, value: row.value }));
}

async function searchTags(call: Call, doctype: string, query: string): Promise<SearchOption[]> {
	const found: string[] = await call("frappe.desk.doctype.tag.tag.get_tags", {
		doctype,
		txt: query.trim(),
	});
	return (found ?? []).map((tag) => ({ label: tag, value: tag }));
}
