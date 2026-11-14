<!--
  "+ Add", opening below itself and aligned to its right edge. Its rows come with the add forms
  (#47416); until then it has none and stays disabled. The bleed sits on the button, so its label
  ends on the pane's 24 px inset like the row content does.
-->
<template>
	<Dropdown :options="options" align="end" side="bottom">
		<Button
			class="-mr-2"
			variant="ghost"
			icon-left="lucide-plus"
			:label="__('Add')"
			:disabled="!options.length"
			data-add
		/>
	</Dropdown>
</template>

<script setup lang="ts">
import { Button, Dropdown, type DropdownOptions } from "frappe-ui";
import { __ } from "@/i18n";

defineProps<{ options: DropdownOptions }>();
</script>
