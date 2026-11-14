<!--
  An Act row on the rail: a button cell shaped like `SidebarRailItem`, with the label as its tooltip.
  It never takes a sidebar and is never current.
-->
<template>
	<Tooltip :text="cell.label" :side="awaySide()">
		<button
			type="button"
			data-slot="sidebar-rail-item"
			:class="CELL"
			:aria-label="cell.label"
			:aria-busy="spinning"
			@click="run"
		>
			<LoadingIndicator v-if="spinning" class="size-4" />
			<Icon v-else-if="cell.icon" :name="cell.icon" />
			<span v-else class="text-sm font-medium">{{ cell.label.charAt(0) }}</span>
		</button>
	</Tooltip>
</template>

<script setup lang="ts">
import { LoadingIndicator, Tooltip } from "frappe-ui";
import Icon from "@/icons/Icon.vue";
import { useActRow } from "./actRow";
import { awaySide } from "./navigationSide";

// `SidebarRailItem`'s own inactive tile.
const CELL =
	"relative flex size-7 shrink-0 items-center justify-center rounded-4 bg-surface-gray-3 text-base transition focus-visible:ring-0 focus-visible:focus-ring";

const props = defineProps<{
	cell: { label: string; icon?: string; act: string; value?: unknown };
}>();

const { spinning, run } = useActRow(() => props.cell);
</script>
