<!--
  Shell story — the integration surface mounted by a host (CRM) on a dev route to
  chase pixel parity with the real list view. It picks a live doctype and hands it
  to `ListViewToolbar`, which constructs the shared `useListView` state and mounts
  the extracted controls into the `ListViewShell`. The `:key="doctype"` remount
  reconstructs `useListView` per doctype — also resetting the controls, no reset watch.

  Story chrome (the doctype picker) uses frappe-ui components, not raw HTML, per
  the workspace convention.
-->
<template>
	<div class="flex flex-col gap-4 p-6">
		<div class="flex items-center gap-2">
			<span class="text-p-sm text-ink-gray-6">Doctype</span>
			<Select v-model="doctype" :options="doctypeOptions" class="w-56" />
		</div>

		<ListViewToolbar :key="doctype" :doctype="doctype" />
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Select } from "frappe-ui";
import ListViewToolbar from "./ListViewToolbar.vue";

const props = withDefaults(defineProps<{ doctype?: string; doctypeOptions?: string[] }>(), {
	doctype: "CRM Lead",
	doctypeOptions: () => ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"],
});

const doctype = ref(props.doctype);
const doctypeOptions = props.doctypeOptions;
</script>
