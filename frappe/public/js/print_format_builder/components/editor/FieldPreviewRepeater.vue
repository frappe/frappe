<template>
	<div v-if="df.label && df.show_label !== 'hide'" class="label">
		{{ df.label }}
	</div>
	<table class="pfb-repeater-table">
		<colgroup>
			<col
				v-for="(col, ci) in df.repeater_columns || []"
				:key="ci"
				:style="col.width ? { width: col.width + '%' } : {}"
			/>
		</colgroup>
		<tbody>
			<tr v-for="(row, i) in (preview_doc[df.source] || []).slice(0, 6)" :key="i">
				<td
					v-for="(col, ci) in df.repeater_columns || []"
					:key="ci"
					class="pfb-repeater-cell"
					:style="{
						textAlign: col.align || 'left',
						...(col.color ? { color: col.color } : {}),
					}"
				>
					{{ repeater_cell(col, i, row) }}
				</td>
			</tr>
			<tr v-if="!(preview_doc[df.source] || []).length">
				<td class="text-muted pfb-table-note">
					{{ df.source ? __("No rows") : __("Pick a source table") }}
				</td>
			</tr>
			<tr v-if="(preview_doc[df.source] || []).length > 6">
				<td :colspan="df.repeater_columns?.length || 1" class="text-muted pfb-table-note">
					{{
						__("+ {0} more rows in this document — all print in the real output", [
							preview_doc[df.source].length - 6,
						])
					}}
				</td>
			</tr>
		</tbody>
	</table>
</template>

<script setup>
import { computed, inject } from "vue";
import { useFieldFormat } from "../../composables/useFieldFormat";

const props = defineProps(["df"]);
const store = inject("$store");
const preview_doc = computed(() => store.preview_doc.value);
const { repeater_cell } = useFieldFormat(props, store, preview_doc);
</script>

<style scoped>
.pfb-table-note {
	text-align: center;
	font-size: 11px;
	padding: 6px;
}
</style>
