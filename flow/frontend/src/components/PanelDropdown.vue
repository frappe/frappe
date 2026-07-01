<script setup>
import { ref, computed, nextTick, watch } from "vue";
import { FeatherIcon } from "@/lib/ui";
import SearchInput from "./SearchInput.vue";
import { __ } from "@/lib/translate";

// Inline dropdown (rendered within #flow-root, never teleported) so its styles
// stay scoped to the panel.
const props = defineProps({
	modelValue: { default: null },
	items: { type: Array, default: () => [] }, // [{ value, label }]
	align: { type: String, default: "left" }, // left | right
	disabled: { type: Boolean, default: false },
	searchable: { type: Boolean, default: false },
});
const emit = defineEmits(["update:modelValue"]);

// Show the search field only once the list is long enough to warrant it.
const SEARCH_THRESHOLD = 7;
const open = ref(false);
const menu = ref(null);
const shift = ref(0);
const query = ref("");

const showSearch = computed(() => props.searchable && props.items.length > SEARCH_THRESHOLD);
const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	if (!q) return props.items;
	return props.items.filter((i) => String(i.label).toLowerCase().includes(q));
});

function toggle() {
	if (props.disabled) return;
	open.value = !open.value;
}
function select(item) {
	emit("update:modelValue", item.value);
	open.value = false;
}

// Keep the menu inside the panel: open aligned to the trigger, then shift it
// horizontally if either edge would spill past #flow-root. Measured once per
// open (a click) — no resize/scroll listeners.
watch(open, async (v) => {
	shift.value = 0;
	if (!v) {
		query.value = "";
		return;
	}
	await nextTick();
	const panel = document.getElementById("flow-root");
	if (!menu.value || !panel) return;
	const m = menu.value.getBoundingClientRect();
	const p = panel.getBoundingClientRect();
	const margin = 8;
	if (m.right > p.right - margin) shift.value = p.right - margin - m.right;
	else if (m.left < p.left + margin) shift.value = p.left + margin - m.left;
});
</script>

<template>
	<div class="relative">
		<slot name="trigger" :toggle="toggle" :open="open" />

		<template v-if="open">
			<div class="fixed inset-0 z-40" @click="open = false"></div>
			<div
				ref="menu"
				class="absolute bottom-[calc(100%+8px)] z-50 w-max min-w-[12rem] max-w-[15rem] overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white shadow-2xl"
				:class="align === 'right' ? 'right-0' : 'left-0'"
				:style="shift ? { transform: `translateX(${shift}px)` } : null"
			>
				<SearchInput
					v-if="showSearch"
					v-model="query"
					:placeholder="__('Search…')"
					autofocus
				/>
				<div class="max-h-80 overflow-y-auto p-1.5 space-y-0.5">
					<button
						v-for="item in filtered"
						:key="item.value ?? '__default'"
						class="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-xs text-ink-gray-8 hover:bg-surface-gray-2"
						:class="{ 'bg-surface-gray-2': item.value === modelValue }"
						@click="select(item)"
					>
						<span class="flex-1 truncate font-medium">{{ item.label }}</span>
						<FeatherIcon
							v-if="item.value === modelValue"
							name="check"
							class="h-4 w-4 shrink-0 text-ink-gray-7"
						/>
					</button>
					<div
						v-if="!filtered.length"
						class="px-3 py-4 text-center text-xs text-ink-gray-5"
					>
						{{ __("No matches") }}
					</div>
				</div>
			</div>
		</template>
	</div>
</template>
