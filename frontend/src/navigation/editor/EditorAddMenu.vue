<!-- "+ Add", below itself and aligned to its right edge; each choice opens that type's form. -->
<template>
	<Dropdown :options="options" align="end" side="bottom">
		<Button
			class="-mr-2"
			variant="ghost"
			icon-left="lucide-plus"
			:label="__('Add')"
			data-add
		/>
	</Dropdown>
</template>

<script setup lang="ts">
import { Button, Dropdown, type DropdownOptions } from "frappe-ui";
import { __ } from "@/i18n";

defineProps<{ options: DropdownOptions }>();
</script>
