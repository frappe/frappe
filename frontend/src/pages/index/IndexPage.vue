<!--
  The index at `/apps`: a filter box over one tile per app. The arrow keys move one selection
  over every section of the page; a section joins it through `sections`.
-->
<template>
	<ScrollArea class="min-h-0 flex-1" data-index>
		<div :class="PAGE_COLUMN">
			<TextInput
				ref="box"
				v-model="query"
				size="lg"
				variant="subtle"
				class="w-full"
				:class="boxWidthClass(apps.length)"
				:placeholder="__('Find an app')"
				:aria-label="__('Find an app')"
				role="combobox"
				aria-autocomplete="list"
				:aria-expanded="listboxes.length > 0"
				:aria-controls="listboxes.join(' ') || undefined"
				:aria-activedescendant="selection.activeId()"
				@keydown="onKeydown"
			>
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
				</template>
			</TextInput>

			<p v-if="!apps.length" class="mt-16 text-base text-ink-gray-5" data-index-state="none">
				{{ __("No apps you can open yet.") }}
			</p>

			<div
				v-else-if="!matches.length"
				class="mt-16 flex flex-col items-center gap-3"
				data-index-state="no-match"
			>
				<p class="text-base text-ink-gray-5">
					{{ __("No app matches “{0}”.", [query.trim()]) }}
				</p>
				<Button :label="__('Clear')" @click="clear" />
			</div>

			<ul
				v-else
				:id="TILES_ID"
				role="listbox"
				:aria-label="__('Apps')"
				class="mt-12 grid gap-x-4 gap-y-6"
				:class="gridClass(matches.length)"
			>
				<li v-for="app in matches" :key="app.app" role="none">
					<AppTile
						:id="selectableId(tileKey(app))"
						:app="app"
						:selected="selection.isSelected(tileKey(app))"
					/>
				</li>
			</ul>

			<IndexFavourites
				v-if="shownFavourites.length"
				:id="FAVOURITES_ID"
				:favourites="shownFavourites"
				:selection="selection"
				:class="boxWidthClass(apps.length)"
			/>
		</div>
	</ScrollArea>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from "vue";
import { Button, ScrollArea, TextInput, type TextInputExposed } from "frappe-ui";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { matching, type IndexApp } from "./apps";
import AppTile from "./AppTile.vue";
import { favouriteKey } from "./favourites";
import IndexFavourites from "./IndexFavourites.vue";
import { PAGE_COLUMN, boxWidthClass, columnsFor, gridClass } from "./grid";
import { Selection, selectableId, type SelectionSection } from "./selection";

const TILES_ID = "index-apps";
const FAVOURITES_ID = "index-favourites";

const boot = inject<Boot>("boot")!;
const apps = boot.apps ?? [];
const favourites = boot.favourites ?? [];

const box = ref<TextInputExposed | null>(null);
const query = ref("");
const matches = computed(() => matching(apps, query.value));
const shownFavourites = computed(() => (query.value.trim() ? [] : favourites));

// In page order. A later section appends its items here and draws `selection.isSelected(key)`.
const sections = computed<SelectionSection[]>(() => [
	{
		items: matches.value.map((app) => ({ key: tileKey(app), href: app.route })),
		columns: columnsFor(matches.value.length),
	},
	{
		items: shownFavourites.value.map((favourite) => ({
			key: favouriteKey(favourite),
			href: favourite.route,
		})),
		columns: 1,
	},
]);
const selection = new Selection(() => sections.value);

const listboxes = computed(() => [
	...(matches.value.length ? [TILES_ID] : []),
	...(shownFavourites.value.length ? [FAVOURITES_ID] : []),
]);

watch(query, (typed) => (typed.trim() ? selection.selectFirst() : selection.clear()));

// Focus stays in the box, so the browser does not scroll to the selection by itself.
watch(selection.selected, (key) => key && scrollIntoView(selectableId(key)), { flush: "post" });

onMounted(() => box.value?.focus());

function onKeydown(event: KeyboardEvent) {
	if (selection.move(event.key)) {
		event.preventDefault();
	} else if (event.key === "Enter" && !event.isComposing) {
		const target = selection.target();
		if (target) window.location.assign(target.href);
	} else if (event.key === "Escape") {
		query.value = "";
	}
}

function clear() {
	query.value = "";
	box.value?.focus();
}

function scrollIntoView(id: string) {
	document.getElementById(id)?.scrollIntoView({ block: "nearest" });
}

function tileKey(app: IndexApp) {
	return `app:${app.app}`;
}
</script>
