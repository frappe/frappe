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
				<!-- Controls mount here as they are extracted (SortBy first). -->
				<span class="text-p-sm text-ink-gray-4">No controls yet</span>
			</template>
		</ListViewShell>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Select } from "frappe-ui";
import { ListViewShell } from "../index";

const props = withDefaults(defineProps<{ doctype?: string; doctypeOptions?: string[] }>(), {
	doctype: "CRM Lead",
	doctypeOptions: () => ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"],
});

const doctype = ref(props.doctype);
const doctypeOptions = props.doctypeOptions;
</script>
