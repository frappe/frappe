<script setup lang="ts">
import { List } from "../index";
import { leadColumns, manyLeads } from "./leads";

// Rows are windowed against the list's own scroll viewport, so a thousand rows mount a
// screenful. `rowHeight` fixes the row height the window needs; the default is 40px.
const rows = manyLeads(1000);
</script>

<template>
	<div class="flex h-80 w-full flex-col">
		<List :columns="leadColumns" :rows="rows" :rowHeight="40" class="px-2" />
	</div>
</template>
