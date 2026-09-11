<!-- The `quick_actions` built-in: `page.quickActions` as buttons, or as icons down the
     collapsed strip. One name, one meaning in both renderings. -->
<template>
	<!-- One tooltip group: the first hover waits for nothing, and the next opens at once.
	     Nothing may shrink: the row has to overflow for the fit to be measurable. -->
	<TooltipProvider v-if="actions.length" :hover-delay="0" :skip-delay="0.5">
		<div
			ref="row"
			class="flex items-center gap-1 [&>*]:shrink-0"
			:class="vertical ? 'flex-col' : ''"
		>
			<!-- Named from the left while the width lasts; the rest keep to their tooltip. -->
			<template v-for="(action, index) in actions.slice(0, visible)" :key="action.name">
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
						<!-- The trigger must own a box: Tooltip drops the attrs the popover anchors on. -->
						<div class="flex shrink-0">
							<Tooltip
								:text="action.label"
								:placement="placement"
								:disabled="index < labelled"
							>
								<Button
									:icon="index < labelled ? undefined : action.icon"
									:icon-left="index < labelled ? action.icon : undefined"
									:label="action.label"
									:variant="vertical ? 'ghost' : 'subtle'"
								/>
							</Tooltip>
						</div>
					</template>
				</TagPicker>

				<Tooltip
					v-else
					:text="action.label"
					:placement="placement"
					:disabled="index < labelled"
				>
					<Button
						:icon="index < labelled ? undefined : action.icon || 'lucide-zap'"
						:icon-left="index < labelled ? action.icon : undefined"
						:label="action.label"
						:variant="vertical ? 'ghost' : 'subtle'"
						@click="context.run(action)"
					/>
				</Tooltip>
			</template>

			<!-- The anchor overlays the trigger, so the picker opens under the menu it came from. -->
			<div v-if="overflow.length" class="relative flex shrink-0">
				<Dropdown :options="overflow" side="bottom" align="end">
					<div class="flex shrink-0">
						<Tooltip text="More quick actions" :placement="placement">
							<Button
								icon="lucide-more-horizontal"
								label="More quick actions"
								variant="subtle"
							/>
						</Tooltip>
					</div>
				</Dropdown>

				<TagPicker
					v-if="taggingOverflowed"
					v-model:open="picking"
					anchored
					:doctype="context.doctype"
					:tags="tags"
					:call="context.controller.page.call"
					@add="people.addTag"
					@remove="people.removeTag"
				/>
			</div>
		</div>
	</TooltipProvider>
</template>

<script setup lang="ts">
import { computed, inject, ref, useTemplateRef, watch } from "vue";
import { Button, Dropdown, Tooltip, TooltipProvider } from "frappe-ui";
import type { QuickAction } from "@/recordPage";
import { PanelContextKey } from "./context";
import { useFittedActions } from "./fittedActions";
import { tagsOf } from "./people";
import { peopleActions } from "./peopleActions";
import TagPicker from "./TagPicker.vue";

const props = defineProps<{ vertical?: boolean }>();

const context = inject(PanelContextKey)!;
const people = peopleActions(context);

const actions = computed(() => context.controller.quickActions.visible());
const tags = computed(() => tagsOf(context.docinfo.value));
const placement = computed(() => (props.vertical ? "left" : "top"));

// The strip has no width to spend, so it names nothing and hides nothing.
const row = useTemplateRef<HTMLElement>("row");
const { labelled, visible } = useFittedActions(
	row,
	() => actions.value.length,
	() => !props.vertical
);

const picking = ref(false);

const overflow = computed(() =>
	actions.value.slice(visible.value).map((action: QuickAction) => ({
		label: action.label,
		icon: action.icon || "lucide-zap",
		onClick: () => (action.tagging ? (picking.value = true) : context.run(action)),
	}))
);

const taggingOverflowed = computed(() =>
	actions.value.slice(visible.value).some((action: QuickAction) => action.tagging)
);

// A pick tags the record and unmounts the anchor mid-open; the flag must not outlive it.
watch(taggingOverflowed, (present) => {
	if (!present) picking.value = false;
});
</script>
