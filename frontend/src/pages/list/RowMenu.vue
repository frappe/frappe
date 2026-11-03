<!-- The "⋯" at the end of a list row; empty when no action applies to the row. -->
<template>
	<Dropdown v-if="options.length" :options="options" side="bottom" align="end">
		<Button
			variant="ghost"
			size="sm"
			icon="lucide-more-horizontal"
			:aria-label="__('Row actions')"
		/>
	</Dropdown>
</template>

<script setup lang="ts">
import { Button, Dropdown } from "frappe-ui";
import type { RowMenuOption } from "./rowActions";

defineProps<{ options: RowMenuOption[] }>();
</script>
