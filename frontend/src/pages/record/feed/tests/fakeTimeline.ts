// A stand-in for the Activity body's store, for the host's paging tests.
import { vi } from "vitest";
import { computed, reactive, ref } from "vue";
import type { ActivityRow } from "@/recordPage";
import type { ActivityTimelineHandle } from "../recordFeeds";

function row(key: string, creation = "2026-09-20 10:00:00"): ActivityRow {
	return { type: "comment", key, timestamp: creation, data: {} };
}

/** A store over `pages`, newest first; `folded` rows load but are never drawn. */
export function fakeTimeline(pages: string[][], { failAt = -1, folded = [] as string[] } = {}) {
	const loaded = ref<ActivityRow[]>(pages[0].map((key) => row(key)));
	const next = ref(1);
	const error = ref<unknown>(null);
	const loading = ref(false);
	const paginate = reactive({
		hasNextPage: computed(() => next.value < pages.length),
		isFetchingNextPage: false,
		fetchNextPage: vi.fn(async () => {
			if (next.value === failAt) {
				error.value = new Error("offline");
				return;
			}
			loaded.value = [...pages[next.value].map((key) => row(key)), ...loaded.value];
			next.value++;
		}),
	});
	const scrollToRow = vi.fn(
		(key: string) => loaded.value.some((one) => one.key === key) && !folded.includes(key)
	);
	const handle: ActivityTimelineHandle = {
		activities: loaded,
		loading,
		error,
		paginate,
		reload: vi.fn(async () => {}),
		scrollToRow,
	};
	return { handle, paginate, scrollToRow, loading };
}
