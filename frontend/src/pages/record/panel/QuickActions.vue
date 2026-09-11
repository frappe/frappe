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
			<!-- The tag action is the picker's own trigger, so it opens where it was pressed. -->
			<TagPicker
				v-if="action.tagging"
				:doctype="context.doctype"
				:tags="tags"
				:call="context.controller.page.call"
				:vertical="vertical"
				@add="people.addTag"
				@remove="people.removeTag"
			>
				<template #trigger>
					<Tooltip v-if="vertical" :text="action.label" placement="left">
						<Button :icon="action.icon" :label="action.label" variant="ghost" />
					</Tooltip>
					<Button
						v-else
						:icon-left="action.icon"
						:label="action.label"
						variant="subtle"
					/>
				</template>
			</TagPicker>
			<Tooltip v-else-if="vertical" :text="action.label" placement="left">
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
import { tagsOf } from "./people";
import { peopleActions } from "./peopleActions";
import TagPicker from "./TagPicker.vue";

defineProps<{ vertical?: boolean }>();

const context = inject(PanelContextKey)!;
const people = peopleActions(context);

const actions = computed(() => context.controller.quickActions.visible());
const tags = computed(() => tagsOf(context.docinfo.value));
</script>
