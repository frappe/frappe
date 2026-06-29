<!--
  Shell story — the integration surface mounted by a host (CRM) on a dev route to
  chase pixel parity with the real list view. It picks a live doctype, hands it to
  the composite `ListViewShell`, and as controls get extracted they mount into the
  shell's `#toolbar` slot here. Today it only proves the wiring: live meta resolves
  inside the host app.

  Story chrome (the doctype picker) uses frappe-ui components, not raw HTML, per
  the workspace convention.
-->
<template>
	<div class="flex flex-col gap-4 p-6">
		<div class="flex items-center gap-2">
			<span class="text-p-sm text-ink-gray-6">Doctype</span>
			<Select v-model="doctype" :options="doctypeOptions" class="w-56" />
		</div>

		<ListViewShell :key="doctype" :doctype="doctype">
			<template #toolbar>
				<!-- Controls mount here as they are extracted. SortBy is the first. -->
				<SortBy v-model="sorts" :doctype="doctype" />
			</template>
		</ListViewShell>

		<div class="text-xs text-ink-gray-6">order_by = "{{ orderBy }}"</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Select } from "frappe-ui";
import { ListViewShell } from "../index";
import { SortBy, serializeOrderBy } from "../../SortBy";
import type { Sort } from "../../SortBy";

const props = withDefaults(defineProps<{ doctype?: string; doctypeOptions?: string[] }>(), {
	doctype: "CRM Lead",
	doctypeOptions: () => ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"],
});

const doctype = ref(props.doctype);
const doctypeOptions = props.doctypeOptions;

// The shell stays a controlled host: it owns the Sort[] and would serialize it to
// `order_by` for a fetch. Reset when the doctype switches (the `:key` remounts).
const sorts = ref<Sort[]>([]);
const orderBy = computed(() => serializeOrderBy(sorts.value));
</script>
