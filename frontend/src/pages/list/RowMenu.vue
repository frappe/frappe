<!-- The "⋯" at the end of a list row; empty when no action applies to the row. -->
<template>
	<Dropdown
		v-if="options.length"
		:options="options.map((option) => withAct(option, option.act))"
		side="bottom"
		align="end"
	>
		<Button
			variant="ghost"
			size="sm"
			icon="lucide-more-horizontal"
			:aria-label="__('Row actions')"
			data-view
		/>
	</Dropdown>
</template>

<script setup lang="ts">
import { Button, Dropdown } from "frappe-ui";
import { withAct } from "@/acts/menuAct";
import type { RowMenuOption } from "./rowActions";

defineProps<{ options: RowMenuOption[] }>();
</script>
