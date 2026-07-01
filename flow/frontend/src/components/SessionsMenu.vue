<script setup>
import { ref, computed, watch } from "vue";
import { Button, FeatherIcon } from "@/lib/ui";
import SearchInput from "./SearchInput.vue";
import { __ } from "@/lib/translate";
import { searchSessions } from "@/api/client";

const props = defineProps({ sessions: { type: Array, default: () => [] } });
const emit = defineEmits(["select"]);

const open = ref(false);
const query = ref("");
const results = ref([]);
const searching = ref(false);

let debounce;
let searchSeq = 0;
watch(query, (q) => {
	clearTimeout(debounce);
	q = q.trim();
	const seq = ++searchSeq; // ignore responses from superseded queries
	if (!q) {
		results.value = [];
		searching.value = false;
		return;
	}
	searching.value = true;
	debounce = setTimeout(async () => {
		try {
			const found = await searchSessions(q);
			if (seq === searchSeq) results.value = found;
		} finally {
			if (seq === searchSeq) searching.value = false;
		}
	}, 250);
});

watch(open, (v) => {
	if (!v) query.value = "";
});

// Server results while searching, otherwise the recent list passed in.
const list = computed(() => (query.value.trim() ? results.value : props.sessions));

function choose(name) {
	open.value = false;
	emit("select", name);
}

function timeAgo(ds) {
	if (!ds) return "";
	return window.moment ? moment(ds).fromNow() : ds;
}
</script>

<template>
	<div class="relative">
		<Button variant="ghost" :title="__('Previous sessions')" @click="open = !open">
			<template #icon>
				<FeatherIcon name="clock" :stroke-width="2" class="h-3.5 w-3.5" />
			</template>
		</Button>

		<template v-if="open">
			<div class="fixed inset-0 z-40" @click="open = false"></div>
			<div
				class="absolute right-0 z-50 mt-1.5 flex w-72 flex-col overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white shadow-2xl"
			>
				<SearchInput v-model="query" :placeholder="__('Search sessions…')">
					<template #trailing>
						<button
							class="flex h-5 w-5 shrink-0 items-center justify-center rounded text-ink-gray-5 hover:bg-surface-gray-2"
							@click="open = false"
						>
							<FeatherIcon name="x" class="h-3.5 w-3.5" />
						</button>
					</template>
				</SearchInput>
				<div class="flow-scrollbar max-h-72 overflow-y-auto p-1">
					<button
						v-for="s in list"
						:key="s.name"
						class="flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left hover:bg-surface-gray-2"
						@click="choose(s.name)"
					>
						<span class="flex-1 truncate text-sm text-ink-gray-8">{{
							s.title || s.name
						}}</span>
						<span class="shrink-0 text-[11px] text-ink-gray-5">{{
							timeAgo(s.modified)
						}}</span>
					</button>
					<div v-if="searching" class="px-2 py-4 text-center text-xs text-ink-gray-5">
						{{ __("Searching…") }}
					</div>
					<div
						v-else-if="!list.length"
						class="px-2 py-4 text-center text-xs text-ink-gray-5"
					>
						{{ query.trim() ? __("No matching sessions") : __("No recent sessions") }}
					</div>
				</div>
			</div>
		</template>
	</div>
</template>
