<!-- An Act row on the rail: `SidebarRailItem` as a button, or a plain tile button on the phone strip. -->
<template>
	<button
		v-if="tile"
		type="button"
		:class="PHONE_TILE"
		:aria-label="cell.label"
		:aria-busy="spinning"
		@click="run"
	>
		<LoadingIndicator v-if="spinning" class="size-4" />
		<Icon v-else-if="cell.icon" :name="cell.icon" />
		<span v-else class="text-sm font-medium">{{ cell.label.charAt(0) }}</span>
	</button>
	<SidebarRailItem v-else :label="cell.label" :aria-busy="spinning" @click="run">
		<LoadingIndicator v-if="spinning" class="size-4" />
		<Icon v-else-if="cell.icon" :name="cell.icon" />
		<span v-else class="text-sm font-medium">{{ cell.label.charAt(0) }}</span>
	</SidebarRailItem>
</template>

<script setup lang="ts">
import { LoadingIndicator, SidebarRailItem } from "frappe-ui";
import Icon from "@/icons/Icon.vue";
import { useActRow } from "./actRow";

const PHONE_TILE =
	"flex size-9 shrink-0 items-center justify-center rounded-4 bg-surface-gray-3 text-base text-ink-gray-8 transition focus-visible:ring-0 focus-visible:focus-ring";

const props = defineProps<{
	cell: { label: string; icon?: string; act: string; value?: unknown };
	tile?: boolean;
}>();

const { spinning, run } = useActRow(() => props.cell);
</script>
