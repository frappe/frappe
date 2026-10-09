<template>
	<Alert
		v-if="previewError && !previewLoading"
		theme="red"
		:title="t('Could not load import file')"
		:description="previewError"
	/>
	<Tabs v-else-if="preview?.tree_preview" v-model="previewTab" :tabs="previewTabs">
		<template #tab-panel="{ tab }">
			<TreePreview
				v-if="tab.value === 'tree'"
				class="pt-3"
				:dataImport="dataImport"
				@select="(rowNumber) => (highlightedRow = rowNumber)"
			/>
			<PreviewTable
				v-else
				class="pt-3"
				:dataImport="dataImport"
				:highlightedRow="highlightedRow"
			/>
		</template>
	</Tabs>
	<PreviewTable v-else-if="preview" :dataImport="dataImport" />
	<div
		v-else-if="previewLoading"
		class="flex w-full flex-col gap-2"
		role="status"
		aria-busy="true"
		:aria-label="t('Loading import preview...')"
	>
		<div class="flex items-center justify-between gap-2">
			<Skeleton class="h-[30px] w-32 rounded" />
			<Skeleton class="h-4 w-[170px] rounded" />
		</div>
		<div class="flex flex-col gap-2 overflow-hidden rounded border border-outline-gray-2 p-2">
			<Skeleton class="h-7 w-full rounded" />
			<Skeleton v-for="i in 8" :key="i" class="h-8 w-full rounded" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Alert, Skeleton, Tabs } from "frappe-ui";
import { computed, ref } from "vue";
import { t } from "../translate";
import type { UseDataImport } from "../useDataImport";
import PreviewTable from "./PreviewTable.vue";
import TreePreview from "./TreePreview.vue";

const props = defineProps<{ dataImport: UseDataImport }>();
const { preview, previewLoading, previewError } = props.dataImport;

const previewTab = ref("tree");
const previewTabs = computed(() => [
	{ value: "tree", label: t("Tree"), iconLeft: "lucide-folder-tree" },
	{ value: "table", label: t("Table"), iconLeft: "lucide-table-2" },
]);
// A click on a tree node marks its row in the table, as Desk does.
const highlightedRow = ref<number | null>(null);
</script>
