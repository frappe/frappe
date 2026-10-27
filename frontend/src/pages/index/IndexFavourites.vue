<!-- The index's Favourites: a chip per favourite record, list or saved view, then More or Less. -->
<template>
	<section class="mt-14 w-full" aria-labelledby="index-favourites-title" data-index-favourites>
		<h2 id="index-favourites-title" class="mb-3 text-sm font-medium text-ink-gray-5">
			{{ __("Favourites") }}
		</h2>
		<ul
			:id="id"
			role="listbox"
			aria-labelledby="index-favourites-title"
			class="flex flex-wrap gap-2"
		>
			<li v-for="chip in chips" :key="chip.key" role="none" class="min-w-0 max-w-full">
				<a
					:id="selectableId(chip.key)"
					:href="chip.favourite.route"
					role="option"
					:aria-selected="chip.selected"
					:title="chip.favourite.title"
					:class="[CHIP, chip.selected ? SELECTED : IDLE]"
					:data-favourite="chip.key"
					:data-kind="chip.favourite.kind"
					:data-selected="chip.selected || undefined"
				>
					<AppLogo
						:logo="chip.favourite.app_logo"
						:title="chip.favourite.app_title"
						:size="16"
					/>
					<span class="truncate">{{ chip.favourite.title }}</span>
				</a>
			</li>
			<li v-if="favourites.hasMore" role="none">
				<button
					:id="selectableId(MORE_FAVOURITES_KEY)"
					type="button"
					role="option"
					tabindex="-1"
					:aria-selected="moreSelected"
					:aria-expanded="favourites.open.value"
					:aria-busy="favourites.loading.value || undefined"
					:class="[CHIP, moreSelected ? SELECTED : IDLE]"
					:data-favourite="MORE_FAVOURITES_KEY"
					:data-selected="moreSelected || undefined"
					@mousedown.prevent
					@click="$emit('toggle')"
				>
					<span class="size-4 text-ink-gray-5" :class="moreIcon" aria-hidden="true" />
					{{ favourites.open.value ? __("Less") : __("More") }}
				</button>
			</li>
		</ul>
	</section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { __ } from "@/i18n";
import AppLogo from "./AppLogo.vue";
import { MORE_FAVOURITES_KEY, favouriteKey, type Favourites } from "./favourites";
import { selectableId, type Selection } from "./selection";

const CHIP =
	"inline-flex h-8 max-w-full items-center gap-2 rounded-4 px-2.5 text-sm text-ink-gray-8 outline-none transition hover:bg-surface-gray-4 focus-visible:focus-ring";
const SELECTED = "bg-surface-gray-4";
const IDLE = "bg-surface-gray-2";

const props = defineProps<{ id: string; favourites: Favourites; selection: Selection }>();
defineEmits<{ toggle: [] }>();

const chips = computed(() =>
	props.favourites.shown.value.map((favourite) => {
		const key = favouriteKey(favourite);
		return { favourite, key, selected: props.selection.isSelected(key) };
	})
);
const moreSelected = computed(() => props.selection.isSelected(MORE_FAVOURITES_KEY));
const moreIcon = computed(() => {
	if (props.favourites.loading.value) return "lucide-loader-circle animate-spin";
	return props.favourites.open.value ? "lucide-chevron-up" : "lucide-chevron-down";
});
</script>
