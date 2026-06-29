<!--
  The list-view integration surface — constructs the shared `useListView` state and
  mounts the extracted controls into the `ListViewShell`. Filter and QuickFilter both
  bind the SAME `filters` ref (the composable's SoT), so setting a quick input updates
  the matching filter condition and vice versa with no wiring here. Mounted under the
  Shell story's `:key="doctype"`, so it (and `useListView`) reconstructs per doctype.

  Toolbar layout: the quick filters take the available width on the left; Filter and
  Sort sit to the right. The shell's `#footer` slot prints the wire output (`order_by`,
  `filters`) a real host would fetch with — below the list — to eyeball the projection
  while chasing pixel parity with CRM.
-->
<template>
	<ListViewShell :doctype="doctype">
		<template #toolbar>
			<QuickFilter
				class="flex-1"
				v-model:filters="view.filters.value"
				v-model:fields="view.quickFilterFields.value"
				v-model:customizing="view.customizing.value"
				:doctype="doctype"
			/>
			<Filter v-model="view.filters.value" :doctype="doctype" />
			<SortBy v-model="view.sorts.value" :doctype="doctype" />
			<Button
				v-if="view.canCustomize.value"
				:icon="view.customizing.value ? 'lucide-check' : 'lucide-settings-2'"
				:tooltip="view.customizing.value ? 'Done' : 'Customize Quick Filters'"
				:variant="view.customizing.value ? 'subtle' : 'ghost'"
				@click="view.customizing.value = !view.customizing.value"
			/>
		</template>

		<template #footer>
			<div class="text-xs text-ink-gray-6">order_by = "{{ view.orderBy.value }}"</div>
			<div class="text-xs text-ink-gray-6">filters = {{ view.wireFilters.value }}</div>
		</template>
	</ListViewShell>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { ListViewShell } from "../index";
import { useListView } from "../useListView";
import { Filter } from "../../Filter";
import { SortBy } from "../../SortBy";
import { QuickFilter } from "../../QuickFilter";

const props = defineProps<{ doctype: string }>();
// `view.customizing` / `view.canCustomize` come from the shared composable, so the
// toggle below works regardless of where it sits — no template ref needed.
const view = useListView(props.doctype);
</script>
