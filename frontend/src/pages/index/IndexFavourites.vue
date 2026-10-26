<!-- The index's Favourites: one chip per favourite record, its app's logo and its title. -->
<template>
	<section class="mt-14 w-full" aria-labelledby="index-favourites-title" data-index-favourites>
		<h2 id="index-favourites-title" class="mb-3 text-sm font-medium text-ink-gray-5">
			{{ __("Favourites") }}
		</h2>
		<ul role="listbox" aria-labelledby="index-favourites-title" class="flex flex-wrap gap-2">
			<li v-for="chip in chips" :key="chip.key" role="none" class="min-w-0 max-w-full">
				<a
					:id="selectableId(chip.key)"
					:href="chip.favourite.route"
					role="option"
					:aria-selected="chip.key === selected"
					:title="chip.favourite.title"
					class="inline-flex h-8 max-w-full items-center gap-2 rounded-4 px-2.5 text-sm text-ink-gray-8 outline-none transition hover:bg-surface-gray-3 focus-visible:focus-ring"
					:class="chip.key === selected ? 'bg-surface-gray-3' : 'bg-surface-gray-2'"
					:data-favourite="chip.key"
					:data-selected="chip.key === selected || undefined"
				>
					<AppLogo
						:logo="chip.favourite.app_logo"
						:title="chip.favourite.app_title"
						:size="16"
					/>
					<span class="truncate">{{ chip.favourite.title }}</span>
				</a>
			</li>
		</ul>
	</section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { __ } from "@/i18n";
import AppLogo from "./AppLogo.vue";
import { favouriteKey, type IndexFavourite } from "./favourites";
import { selectableId } from "./selection";

const props = defineProps<{ favourites: IndexFavourite[]; selected: string | null }>();

const chips = computed(() =>
	props.favourites.map((favourite) => ({ favourite, key: favouriteKey(favourite) }))
);
</script>
