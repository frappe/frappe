<script setup lang="ts" generic="T extends SearchResult">
import { ref } from "vue";
import { Icon, TextInput } from "frappe-ui";
import { List, ListCell, ListRow, ListRows } from "frappe-ui/list";
import { translate as __ } from "../utils/translate";
import type { SearchProps, SearchResult } from "./types";

defineProps<SearchProps<T>>();

defineEmits<{ select: [item: T, event: MouseEvent] }>();

const query = defineModel<string>("query", { default: "" });

const input = ref<HTMLElement | null>(null);

defineExpose({
	focus: () => input.value?.querySelector("input")?.focus(),
});
</script>

<template>
	<div data-slot="search" class="h-full overflow-y-auto pb-10">
		<div ref="input" data-slot="search-input" class="px-4 pt-3 pb-2">
			<TextInput
				v-model="query"
				:placeholder="placeholder ?? __('Search')"
				:aria-label="__('Search')"
			>
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
				</template>
			</TextInput>
		</div>

		<slot name="header" :query="query" />

		<div class="px-2">
			<List v-if="results.length" :row-height="52">
				<ListRows
					:items="results"
					:row-key="(_, index) => index"
					v-slot="{ item, index, value }"
				>
					<ListRow :value="value" @click="(event) => $emit('select', item, event)">
						<ListCell>
							<slot name="item-prefix" :item="item" :index="index">
								<Icon
									:name="item.icon || 'lucide-search'"
									class="size-5 text-ink-gray-6"
								/>
							</slot>
						</ListCell>
						<ListCell>
							<div class="min-w-0">
								<slot name="item-label" :item="item" :index="index">
									<p class="truncate text-base text-ink-gray-8">
										{{ item.label }}
									</p>
									<p
										v-if="item.description"
										class="truncate text-xs text-ink-gray-5"
									>
										{{ item.description }}
									</p>
								</slot>
							</div>
						</ListCell>
						<ListCell v-if="$slots['item-suffix']" class="justify-end">
							<slot name="item-suffix" :item="item" :index="index" />
						</ListCell>
					</ListRow>
				</ListRows>
			</List>

			<slot v-else-if="loading" name="loading" />

			<slot v-else name="empty" :query="query">
				<p data-slot="search-empty" class="py-14 text-center text-base text-ink-gray-6">
					{{
						query.trim()
							? __("Nothing matches {0}", [query.trim()])
							: __("Nothing to show")
					}}
				</p>
			</slot>
		</div>
	</div>
</template>
