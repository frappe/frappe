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
				:class="boxWidth"
				:placeholder="__('Find an app')"
				:aria-label="__('Find an app')"
				role="combobox"
				aria-autocomplete="list"
				:aria-expanded="listboxes.length > 0"
				:aria-controls="listboxes.join(' ') || undefined"
				:aria-activedescendant="selection.activeId()"
				:readonly="arranging"
				@keydown="onKeydown"
			>
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
				</template>
			</TextInput>

			<p v-if="!apps.length" class="mt-16 text-base text-ink-gray-5" data-index-state="none">
				{{ __("No apps you can open yet.") }}
			</p>

			<ArrangeApps
				v-else-if="arranging"
				:apps="apps"
				:box-width-class="boxWidth"
				@done="finishArranging"
			/>

			<div
				v-else-if="!matches.length && !query.trim()"
				class="mt-16 flex flex-col items-center gap-3"
				data-index-state="all-hidden"
			>
				<p class="text-base text-ink-gray-5">{{ __("You have hidden every app.") }}</p>
				<Button :label="__('Arrange apps')" @click="startArranging" />
			</div>

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
				:class="gridClass(tileCount)"
			>
				<li v-for="app in matches" :key="app.app" role="none" class="group/tile relative">
					<AppTile
						:id="selectableId(tileKey(app))"
						:app="app"
						:selected="selection.isSelected(tileKey(app))"
					/>
					<div
						class="absolute right-2 top-0 opacity-0 transition group-hover/tile:opacity-100 has-[[data-state=open]]:opacity-100"
					>
						<Dropdown :options="tileMenu(app)" side="bottom" align="end">
							<button
								type="button"
								class="flex size-6 items-center justify-center rounded-full bg-surface-white text-ink-gray-7 shadow ring-1 ring-outline-gray-2 hover:bg-surface-gray-2 focus-visible:focus-ring"
								:aria-label="__('{0} options', [app.title])"
								tabindex="-1"
								data-tile-menu
							>
								<span class="lucide-ellipsis size-3.5" aria-hidden="true" />
							</button>
						</Dropdown>
					</div>
				</li>
				<li v-if="moreApps" role="none">
					<MoreAppsTile
						:id="selectableId(MORE_APPS_KEY)"
						:href="moreApps"
						:selected="selection.isSelected(MORE_APPS_KEY)"
					/>
				</li>
			</ul>

			<IndexFavourites
				v-if="shownFavourites.length"
				:id="FAVOURITES_ID"
				:favourites="shownFavourites"
				:selection="selection"
				:class="boxWidth"
			/>

			<IndexRecent
				v-if="shownRecent.length"
				:id="RECENT_ID"
				:recent="shownRecent"
				:selection="selection"
				:site-zone="boot.session.timezone"
				:class="boxWidth"
			/>
		</div>

		<IndexNotices v-if="hasNotices" :notices="notices" :user="boot.session.user.name" />
	</ScrollArea>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, inject, onMounted, ref, watch } from "vue";
import { Button, Dropdown, ScrollArea, TextInput, toast, type TextInputExposed } from "frappe-ui";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { usePageMenuItems } from "@/shell/pageMenu";
import { matching, unfilteredTiles, type IndexApp } from "./apps";
import AppTile from "./AppTile.vue";
import { favouriteKey } from "./favourites";
import IndexFavourites from "./IndexFavourites.vue";
import IndexRecent from "./IndexRecent.vue";
import { PAGE_COLUMN, boxWidthClass, columnsFor, gridClass } from "./grid";
import { saveLayer } from "./layer";
import MoreAppsTile from "./MoreAppsTile.vue";
import { recentKey } from "./recent";
import { Selection, selectableId, type SelectionSection } from "./selection";

const ArrangeApps = defineAsyncComponent(() => import("./ArrangeApps.vue"));
const IndexNotices = defineAsyncComponent(() => import("./IndexNotices.vue"));

const TILES_ID = "index-apps";
const FAVOURITES_ID = "index-favourites";
const RECENT_ID = "index-recent";
const MORE_APPS_KEY = "more-apps";

const boot = inject<Boot>("boot")!;
const apps = ref<IndexApp[]>(boot.apps ?? []);
const favourites = boot.favourites ?? [];
const recent = boot.recent ?? [];
const notices = boot.notices ?? {};
const hasNotices = Object.keys(notices).length > 0;

const box = ref<TextInputExposed | null>(null);
const query = ref("");
const arranging = ref(false);
const matches = computed(() => (arranging.value ? [] : matching(apps.value, query.value)));
// Never a filter match, and only with the grid: the arrow keys must not reach an undrawn item.
const moreApps = computed(() =>
	matches.value.length && !query.value.trim() ? boot.more_apps ?? null : null
);
const tileCount = computed(() => matches.value.length + (moreApps.value ? 1 : 0));
const shownFavourites = computed(() => (query.value.trim() || arranging.value ? [] : favourites));
const shownRecent = computed(() => (query.value.trim() || arranging.value ? [] : recent));
// Arranging draws every app, hidden ones too, and no "Get more apps" tile.
const boxWidth = computed(() =>
	boxWidthClass(
		arranging.value ? apps.value.length : unfilteredTiles(apps.value, boot.more_apps)
	)
);

if (apps.value.length) {
	usePageMenuItems([
		{ label: __("Arrange apps"), icon: "lucide-layout-grid", onClick: startArranging },
	]);
}

// In page order. A later section appends its items here and draws `selection.isSelected(key)`.
const sections = computed<SelectionSection[]>(() => [
	{
		items: [
			...matches.value.map((app) => ({ key: tileKey(app), href: app.route })),
			...(moreApps.value ? [{ key: MORE_APPS_KEY, href: moreApps.value }] : []),
		],
		columns: columnsFor(tileCount.value),
	},
	{
		items: shownFavourites.value.map((favourite) => ({
			key: favouriteKey(favourite),
			href: favourite.route,
		})),
		columns: 1,
	},
	{
		items: shownRecent.value.map((visit, position) => ({
			key: recentKey(position),
			href: visit.route,
		})),
		columns: 1,
	},
]);
const selection = new Selection(() => sections.value);

const listboxes = computed(() => [
	...(matches.value.length ? [TILES_ID] : []),
	...(shownFavourites.value.length ? [FAVOURITES_ID] : []),
	...(shownRecent.value.length ? [RECENT_ID] : []),
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

function startArranging() {
	query.value = "";
	arranging.value = true;
}

function finishArranging(arranged: IndexApp[]) {
	apps.value = arranged;
	arranging.value = false;
	box.value?.focus();
}

function tileMenu(app: IndexApp) {
	return app.hidden
		? [{ label: __("Show"), icon: "lucide-eye", onClick: () => setHidden(app, false) }]
		: [{ label: __("Hide"), icon: "lucide-eye-off", onClick: () => setHidden(app, true) }];
}

async function setHidden(app: IndexApp, hidden: boolean) {
	flag(app, hidden);
	try {
		await saveLayer(apps.value);
	} catch (error) {
		flag(app, !hidden);
		toast.error(__("Could not save your apps: {0}", [(error as Error).message]));
	}
}

function flag(app: IndexApp, hidden: boolean) {
	apps.value = apps.value.map((entry) => (entry.app === app.app ? { ...entry, hidden } : entry));
}

function scrollIntoView(id: string) {
	document.getElementById(id)?.scrollIntoView({ block: "nearest" });
}

function tileKey(app: IndexApp) {
	return `app:${app.app}`;
}
</script>
