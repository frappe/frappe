// Options matched on the server as the reader types, for the assign, share and tag pickers.
import { computed, ref, type Ref } from "vue";
import { useDebounceFn } from "@vueuse/core";
import { errorMessage } from "@/recordPage";

export type SearchOption = { label: string; value: string; image?: string };

type Call = (method: string, params?: Record<string, any>) => Promise<any>;

const PAGE_LENGTH = 10;

export function useUserSearch(call: Call, pinned: Ref<SearchOption[]>) {
	return useRemoteSearch((query) => searchUsers(call, query), pinned);
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

async function searchUsers(call: Call, query: string): Promise<SearchOption[]> {
	const rows: any[] = await call("frappe.client.get_list", {
		doctype: "User",
		fields: ["name", "full_name", "user_image"],
		filters: [
			["enabled", "=", 1],
			["user_type", "=", "System User"],
			["name", "not in", ["Administrator", "Guest"]],
		],
		or_filters: query
			? [
					["full_name", "like", `%${query}%`],
					["name", "like", `%${query}%`],
			  ]
			: undefined,
		order_by: "full_name asc",
		limit_page_length: PAGE_LENGTH,
	});
	return rows.map((row) => ({
		label: row.full_name || row.name,
		value: row.name,
		image: row.user_image || "",
	}));
}

async function searchTags(call: Call, doctype: string, query: string): Promise<SearchOption[]> {
	const found: string[] = await call("frappe.desk.doctype.tag.tag.get_tags", {
		doctype,
		txt: query.trim(),
	});
	return (found ?? []).map((tag) => ({ label: tag, value: tag }));
}
