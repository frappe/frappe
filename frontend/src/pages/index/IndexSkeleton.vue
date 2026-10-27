<!-- The index while its code loads: the filter box at its final width, and four tiles. -->
<template>
	<div class="flex min-h-0 flex-1 flex-col" data-index-skeleton>
		<LoadingStatus />
		<div :class="PAGE_COLUMN">
			<TextInput
				size="lg"
				variant="subtle"
				class="w-full"
				:class="boxWidthClass(unfilteredTiles(boot.apps ?? [], boot.more_apps))"
				:placeholder="__('Find an app')"
				readonly
				tabindex="-1"
			>
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
				</template>
			</TextInput>

			<div class="mt-12 grid gap-x-4 gap-y-6" :class="gridClass(TILES)">
				<div
					v-for="tile in TILES"
					:key="tile"
					class="flex flex-col items-center gap-2 p-2"
				>
					<Skeleton class="size-14 rounded-[22%]" />
					<Skeleton class="h-3 w-16 rounded-2" />
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { inject } from "vue";
import { Skeleton, TextInput } from "frappe-ui";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import LoadingStatus from "@/shell/LoadingStatus.vue";
import { unfilteredTiles } from "./apps";
import { PAGE_COLUMN, boxWidthClass, gridClass } from "./grid";

const TILES = 4;

// A page's props reach its loading state too; they mean nothing here.
defineOptions({ inheritAttrs: false });

const boot = inject<Boot>("boot")!;
</script>
