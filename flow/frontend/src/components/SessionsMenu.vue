<script setup>
import { ref } from "vue";
import { Button, FeatherIcon } from "@/lib/ui";
import { __ } from "@/lib/translate";

defineProps({ sessions: { type: Array, default: () => [] } });
const emit = defineEmits(["select"]);

const open = ref(false);

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
				<div class="flex items-center border-b border-outline-gray-1 py-2 pl-3 pr-2">
					<span class="flex-1 text-xs font-medium text-ink-gray-7">
						{{ __("Recent sessions") }}
					</span>
					<button
						class="flex h-5 w-5 items-center justify-center rounded text-ink-gray-5 hover:bg-surface-gray-2"
						@click="open = false"
					>
						<FeatherIcon name="x" class="h-3.5 w-3.5" />
					</button>
				</div>
				<div class="flow-scrollbar max-h-72 overflow-y-auto p-1">
					<button
						v-for="s in sessions"
						:key="s.name"
						class="flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left hover:bg-surface-gray-2"
						@click="choose(s.name)"
					>
						<span class="flex-1 truncate text-sm text-ink-gray-8">{{
							s.title || s.name
						}}</span>
						<span class="shrink-0 text-[11px] text-ink-gray-5">{{
							timeAgo(s.creation)
						}}</span>
					</button>
					<div
						v-if="!sessions.length"
						class="px-2 py-4 text-center text-xs text-ink-gray-5"
					>
						{{ __("No recent sessions") }}
					</div>
				</div>
			</div>
		</template>
	</div>
</template>
