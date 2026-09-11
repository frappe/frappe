<!-- The `quick_actions` built-in: `page.quickActions` as buttons, or as icons down the
     collapsed strip. One name, one meaning in both renderings. -->
<template>
	<!-- Nothing to draw takes no room: the section's body hides itself when empty. -->
	<div
		v-if="actions.length"
		class="flex gap-1"
		:class="vertical ? 'flex-col items-center' : 'flex-wrap'"
	>
		<template v-for="action in actions" :key="action.name">
			<Tooltip v-if="vertical" :text="action.label" placement="left">
				<Button
					:icon="action.icon || 'lucide-zap'"
					:label="action.label"
					variant="ghost"
					@click="context.run(action)"
				/>
			</Tooltip>
			<Button
				v-else
				:icon-left="action.icon"
				:label="action.label"
				variant="subtle"
				@click="context.run(action)"
			/>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Button, Tooltip } from "frappe-ui";
import { PanelContextKey } from "./context";

defineProps<{ vertical?: boolean }>();

const context = inject(PanelContextKey)!;

const actions = computed(() => context.controller.quickActions.visible());
</script>
