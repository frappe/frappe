<!-- Reset all customizations: what the reset removes and what it keeps, with the server's counts.
     It closes with `true` to reset. -->
<template>
	<div class="flex flex-col gap-4 text-p-base text-ink-gray-7" data-reset-all-dialog>
		<template v-if="removes.length">
			<div class="flex flex-col gap-2">
				<p>{{ __("Removes what this site changed:") }}</p>
				<ul class="flex flex-col gap-1.5">
					<li v-for="line in removes" :key="line" class="flex items-center gap-2">
						<Icon name="lucide-minus" class="size-4 shrink-0 text-ink-gray-5" />{{
							line
						}}
					</li>
				</ul>
			</div>
			<p>
				{{
					__(
						"The custom fields' values stay in the database. {0} looks as {1} ships it.",
						[doctype, appTitle || __("its app")]
					)
				}}
			</p>
			<p v-if="dirty">{{ __("Your edits that are not saved are dropped too.") }}</p>
		</template>
		<p v-else>{{ __("This site has not changed {0}. Nothing to reset.", [doctype]) }}</p>
		<p v-if="keeps.length" class="text-ink-gray-6">
			{{
				__("Keeps {0}: {1} made them, and they come back on every migrate.", [
					keeps.join(", "),
					appTitle || __("An app"),
				])
			}}
		</p>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" autofocus @click="close(null)" />
			<Button
				variant="solid"
				theme="red"
				:label="__('Reset all')"
				:disabled="!removes.length"
				@click="close(true)"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Icon } from "frappe-ui";
import { __ } from "@/i18n";
import { resetLines, type ResetCounts } from "./customizeActs";
import { returnToMore } from "./returnToMore";

const props = defineProps<{
	doctype: string;
	appTitle: string | null;
	counts: ResetCounts;
	dirty: boolean;
	close: (reset: true | null) => void;
}>();

returnToMore();

const removes = computed(() => resetLines(props.counts.delete));
const keeps = computed(() => resetLines(props.counts.keep));
</script>
