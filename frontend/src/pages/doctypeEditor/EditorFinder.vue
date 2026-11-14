<!-- The header's finder: a search button and the popover below it, aligned to its right edge. The
     act "Find a field or setting" (Mod+J) toggles it. -->
<template>
	<Popover v-model:open="open" side="bottom" align="end">
		<template #trigger>
			<button
				type="button"
				class="flex h-7 shrink-0 items-center gap-2 rounded-4 bg-surface-gray-2 px-2 max-[1343px]:w-7 max-[1343px]:justify-center max-[1343px]:px-0 min-[1344px]:w-[336px] text-base text-ink-gray-6 hover:bg-surface-gray-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				aria-keyshortcuts="Control+J Meta+J"
				:aria-label="placeholder"
				:title="placeholder"
				data-editor-finder
			>
				<span class="lucide-search size-4 shrink-0" aria-hidden="true" />
				<span class="flex-1 truncate text-left max-[1343px]:hidden">{{
					placeholder
				}}</span>
				<KeyboardShortcut combo="Mod+J" class="max-[1343px]:hidden" />
			</button>
		</template>
		<div class="flex w-[400px] flex-col" data-editor-finder-content>
			<div class="p-1.5 pb-0">
				<TextInput
					v-model="query"
					:placeholder="placeholder"
					:aria-label="placeholder"
					:title="placeholder"
					autofocus
					@keydown.down.prevent="move(1)"
					@keydown.up.prevent="move(-1)"
					@keydown.enter.prevent="enter"
				>
					<template #prefix>
						<span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
					</template>
				</TextInput>
			</div>
			<div ref="list" class="flex max-h-[420px] flex-col overflow-y-auto p-1.5">
				<div v-for="group in groups" :key="group.label" class="flex flex-col gap-px">
					<p
						class="flex h-7 shrink-0 items-center px-2 text-sm font-medium leading-tighter text-ink-gray-6"
					>
						{{ group.label }}
					</p>
					<ItemListRow
						v-for="item in group.items"
						:key="item.key"
						as="button"
						type="button"
						class="shrink-0 text-left"
						:active="items[active]?.key === item.key"
						:data-finder-row="item.key"
						@mousemove="active = items.indexOf(item)"
						@click="pick(item)"
					>
						<span class="block truncate text-ink-gray-8" :title="item.label">{{
							item.label
						}}</span>
						<template v-if="item.suffix" #suffix>
							<span
								class="max-w-32 truncate text-sm leading-tighter text-ink-gray-7"
								:title="item.suffix"
								>{{ item.suffix }}</span
							>
						</template>
					</ItemListRow>
				</div>
				<p v-if="!items.length" class="px-2 py-1.5 text-base text-ink-gray-6">
					{{ __("Nothing matches “{0}”.", [query.trim()]) }}
				</p>
			</div>
		</div>
	</Popover>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { ItemListRow, KeyboardShortcut, Popover, TextInput } from "frappe-ui";
import { __ } from "@/i18n";
import { finderGroups, type FinderHost, type FinderItem } from "./editorFinder";

const props = defineProps<{ host: FinderHost }>();
const open = defineModel<boolean>("open", { required: true });
const query = ref("");
const active = ref(0);
const list = ref<HTMLElement>();

const placeholder = __("Search fields, settings, properties");
const groups = computed(() => finderGroups(props.host, query.value));
const items = computed(() => groups.value.flatMap((group) => group.items));

function pick(item: FinderItem) {
	open.value = false;
	item.pick();
}

function enter() {
	const item = items.value[active.value];
	if (item) pick(item);
}

function move(by: number) {
	if (!items.value.length) return;
	active.value = (active.value + by + items.value.length) % items.value.length;
	const key = items.value[active.value].key;
	void nextTick(() =>
		list.value
			?.querySelector(`[data-finder-row="${key}"]`)
			?.scrollIntoView({ block: "nearest" })
	);
}

watch(query, () => (active.value = 0));
watch(open, (now) => {
	if (now) return;
	query.value = "";
	active.value = 0;
});
</script>
