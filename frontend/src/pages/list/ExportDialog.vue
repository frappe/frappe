<!-- The bulk Export: the Data Exporter on the selected records, or on every record the filters show. -->
<template>
	<TemplateModal
		v-model:open="open"
		:doctype="doctype"
		importType="Insert New Records"
		:providerSchema="null"
		:doctypeMeta="meta"
		:pinned="pinned"
	/>
</template>

<script setup lang="ts">
import { fetchDoctypeBundle, TemplateModal } from "@framework/ui/ExportTemplate";
import { computed, ref } from "vue";
import type { BulkSelection } from "@framework/ui/api";
import { exportFilters } from "@/list/bulkExport";

const props = defineProps<{ doctype: string; selection: BulkSelection; count: number }>();
const open = defineModel<boolean>({ default: false });

const meta = ref<Awaited<ReturnType<typeof fetchDoctypeBundle>> | null>(null);
fetchDoctypeBundle(props.doctype)
	.then((bundle) => (meta.value = bundle))
	.catch(() => (meta.value = null));

const pinned = computed(() => ({
	filters: exportFilters(props.selection) ?? {},
	count: props.count,
}));
</script>
