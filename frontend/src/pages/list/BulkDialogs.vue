<!-- The bulk bar's dialogs that every renderer shares: Print, Edit, Export and the collaboration ones. -->
<template>
	<component
		:is="parts.chunk.PrintDialog"
		v-if="parts.print.mounted.value"
		v-model="parts.print.open.value"
		:doctype="doctype"
		:count="parts.print.count.value"
		:all="parts.print.all.value"
		:approx="parts.print.approx.value"
		:scope="parts.print.scope.value"
	/>
	<component
		:is="parts.chunk.EditDialog"
		v-if="parts.output.edit.mounted.value"
		v-model="parts.output.edit.open.value"
		:doctype="doctype"
		:count="scope.count.value"
		:all="scope.all.value"
		:approx="scope.approx.value"
		:run="parts.output.runEdit"
	/>
	<component
		:is="parts.chunk.ExportDialog"
		v-if="parts.output.export.mounted.value"
		v-model="parts.output.export.open.value"
		:doctype="doctype"
		:selection="parts.output.export.selection.value"
		:count="scope.count.value"
	/>
	<component
		:is="parts.CollabDialog"
		v-if="parts.collab.request.value"
		:request="parts.collab.request.value"
		:doctype="doctype"
		:reload="reload"
		:select="select"
		@close="parts.collab.request.value = null"
	/>
</template>

<script setup lang="ts">
import type { BulkScope } from "@/list/useBulkScope";
import type { LoadedBulkBar } from "./useBulkBar";

defineProps<{
	parts: LoadedBulkBar;
	scope: BulkScope;
	doctype: string;
	reload: () => void;
	/** Selects the records a collaboration run names, such as the ones it failed on. */
	select: (names: string[]) => void;
}>();
</script>
