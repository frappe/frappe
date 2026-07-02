<!--
  Shell story — the integration surface mounted by a host (CRM) on a dev route to
  chase pixel parity with the real list view. It picks a live doctype and hands it
  to `ListViewToolbar`, which constructs the shared `useListView` state and mounts
  the extracted controls into the `ListViewShell`. The `:key="doctype"` remount
  reconstructs `useListView` per doctype — also resetting the controls, no reset watch.

  Story chrome (the doctype picker) uses frappe-ui components, not raw HTML, per
  the workspace convention. The "Synthetic column" switch declares a host Record-
  indicator column (ADR-0033) and folds it into the list — it appears after the
  title (subsuming the raw `status` field), shows in ColumnSettings (toggle / re-add),
  rides the wire `columns` readout, and is never requested from `get_list`; its cell
  is drawn by the host (a representative badge here — see ListViewToolbar).
-->
<template>
	<!-- `h-full` fills the layout's content area so the list gets a finite height
	     to distribute (toolbar/footer fixed, rows scroll). `min-h-0` lets the flex
	     children shrink rather than overflow the page. -->
	<div class="flex h-full min-h-0 flex-col gap-4 p-6">
		<div class="flex shrink-0 items-center gap-4">
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Doctype</span>
				<Select v-model="doctype" :options="doctypeOptions" class="w-56" />
			</div>
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">Synthetic column</span>
				<Switch v-model="showSynthetic" />
			</div>
		</div>

		<ListViewToolbar :key="doctype" :doctype="doctype" :synthetic-demo="showSynthetic" />
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Select, Switch } from "frappe-ui";
import ListViewToolbar from "./ListViewToolbar.vue";

const props = withDefaults(defineProps<{ doctype?: string; doctypeOptions?: string[] }>(), {
	doctype: "CRM Lead",
	doctypeOptions: () => ["CRM Lead", "CRM Deal", "CRM Task", "ToDo", "DocType"],
});

const doctype = ref(props.doctype);
const doctypeOptions = props.doctypeOptions;
const showSynthetic = ref(false);
</script>
