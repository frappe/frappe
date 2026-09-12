<!--
  The record's header row, drawn from `page.header`: crumbs and the favourite star left;
  controls, `⋯` and Save right, in the projection's order, with the menu slotted in at Save's
  left hand. A div, not a header: it fills the frame's pinned row, which is the `<header>` element.
-->
<template>
	<div class="flex min-w-0 flex-1 items-center justify-between gap-3">
		<nav class="flex min-w-0 items-center gap-1 text-base">
			<template v-for="(control, index) in projection.left" :key="control.item.name">
				<span
					v-if="isCrumb(control) && isCrumb(projection.left[index - 1])"
					class="text-ink-gray-4"
				>
					/
				</span>

				<RouterLink
					v-if="isCrumb(control) && control.item.href && !control.item.run"
					:to="control.item.href"
					class="truncate text-ink-gray-5 hover:text-ink-gray-8"
				>
					{{ control.item.label }}
				</RouterLink>
				<button
					v-else-if="isCrumb(control) && control.item.run"
					type="button"
					class="truncate text-ink-gray-5 hover:text-ink-gray-8"
					@click="run(control.item)"
				>
					{{ control.item.label }}
				</button>
				<span v-else-if="isCrumb(control)" class="truncate font-medium text-ink-gray-9">
					{{ control.item.label }}
				</span>

				<RecordFavourite
					v-else-if="control.item.name === 'favourite'"
					:favourites="favourites"
					:favourited="favourited"
					@toggle="run(control.item)"
				/>

				<Dropdown
					v-else-if="control.kind === 'dropdown'"
					:options="menuContent(control.members, run)"
					side="bottom"
					align="start"
				>
					<div class="flex shrink-0">
						<Button
							:label="control.item.label"
							:icon-left="control.item.icon"
							icon-right="lucide-chevron-down"
							variant="ghost"
						/>
					</div>
				</Dropdown>

				<Button
					v-else
					:label="control.item.label"
					:icon-left="control.item.icon"
					variant="ghost"
					@click="run(control.item)"
				/>
			</template>
		</nav>

		<div class="flex shrink-0 items-center gap-2">
			<template v-for="control in rightHand" :key="control.item.name">
				<Dropdown v-if="control === MENU" :options="bands" side="bottom" align="end">
					<div class="flex shrink-0">
						<Button
							icon="lucide-more-horizontal"
							variant="subtle"
							label="More actions"
						/>
					</div>
				</Dropdown>

				<RecordFavourite
					v-else-if="control.item.name === 'favourite'"
					:favourites="favourites"
					:favourited="favourited"
					@toggle="run(control.item)"
				/>

				<Dropdown
					v-else-if="control.kind === 'dropdown'"
					:options="menuContent(control.members, run)"
					side="bottom"
					align="end"
				>
					<!-- The trigger must own a box: a display:contents wrapper anchors the menu at 0,0. -->
					<div class="flex shrink-0">
						<Button
							:label="control.item.label"
							:icon-left="control.item.icon"
							icon-right="lucide-chevron-down"
							variant="subtle"
						/>
					</div>
				</Dropdown>

				<Tooltip
					v-else-if="control.item.name === 'save'"
					text="No changes to save"
					:disabled="dirty"
				>
					<!-- A disabled button fires no pointer events, so the wrapper owns the box the tooltip hovers on. -->
					<div class="flex shrink-0">
						<Button
							:label="control.item.label"
							:icon-left="control.item.icon"
							variant="solid"
							:disabled="!dirty"
							:loading="saving"
							@click="run(control.item)"
						/>
					</div>
				</Tooltip>

				<Button
					v-else
					:label="control.item.label"
					:icon-left="control.item.icon"
					variant="subtle"
					@click="run(control.item)"
				/>
			</template>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { Button, Dropdown, Tooltip } from "frappe-ui";
import type { HeaderControl, HeaderItem, HeaderProjection } from "@/recordPage";
import { bandRows, menuContent } from "./headerMenuOptions";
import type { Person } from "./panel/people";
import RecordFavourite from "./RecordFavourite.vue";

const props = defineProps<{
	projection: HeaderProjection;
	dirty: boolean;
	saving: boolean;
	/** Who favourited the record and whether the reader did, for the `favourite` built-in. */
	favourites: Person[];
	favourited: boolean;
}>();

const emit = defineEmits<{ run: [item: HeaderItem] }>();
const router = useRouter();

// Bands are `MenuGroupOption`s, and a band shows a heading only when its container was declared.
const bands = computed(() =>
	props.projection.bands.map((band) => ({
		group: band.label ?? band.group,
		hideLabel: !band.label,
		options: bandRows(band.items, run),
	}))
);

// The menu's own row in the controls: at Save's left hand, or last when a script hid Save.
const MENU = { kind: "button", item: { name: "more", label: "More actions" } } as HeaderControl;

const rightHand = computed(() => {
	const controls = props.projection.controls;
	if (!props.projection.bands.length) return controls;
	const at = controls.findIndex((control) => control.item.name === "save");
	if (at < 0) return [...controls, MENU];
	return [...controls.slice(0, at), MENU, ...controls.slice(at)];
});

function isCrumb(control?: HeaderControl) {
	return control?.kind === "crumb";
}

// `run` wins over `href`; an item with only an `href` is a link wherever it renders.
function run(item: HeaderItem) {
	if (!item.run && item.href) {
		router.push(item.href);
		return;
	}
	emit("run", item);
}
</script>
