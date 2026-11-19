<!-- The rows area of a view type that is not built yet; loaded on demand, so the list page's JS does not carry it. -->
<template>
	<PageState
		name="empty"
		icon="lucide-construction"
		:title="__('{0} view is not built yet', [label])"
		:description="__('Use the List view until it is ready.')"
	>
		<Button
			class="mt-1"
			:label="__('Open the List view')"
			:route="routeFor(doctype, null, { view: 'list' })"
		/>
	</PageState>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { __ } from "@/i18n";
import { routeFor } from "@/router/routeFor";
import PageState from "@/shell/PageState.vue";

defineProps<{ doctype: string; label: string }>();
</script>
