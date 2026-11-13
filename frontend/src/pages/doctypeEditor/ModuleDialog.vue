<!-- The Danger zone's Move and Make standard: the module, and what happens to the files. A standard
     DocType, or one made standard, goes in an app's module. It closes with the module. -->
<template>
	<div class="flex flex-col gap-4" :data-module-dialog="standard ? 'standard' : 'move'">
		<Combobox
			v-model="picked"
			:label="__('Module')"
			:options="modules"
			:placeholder="__('Choose a module')"
		/>
		<p class="text-p-base text-ink-gray-7">{{ consequence }}</p>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button
				variant="solid"
				:label="standard ? __('Make standard') : __('Move')"
				:disabled="!picked"
				@click="close(picked)"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Button, Combobox, toast } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";

const props = defineProps<{
	doctype: string;
	/** The module it is in now. */
	module: string;
	custom: boolean;
	/** Make standard: its files go in the module's app, for good. */
	standard: boolean;
	close: (module: string | null) => void;
}>();

const picked = ref<string | null>(null);
const modules = ref<{ label: string; value: string; description?: string }[]>([]);
// The files go in an app: only a custom DocType that stays custom may move to a site's own module.
const appModules = props.standard || !props.custom;

const consequence = computed(() => {
	if (props.standard)
		return __(
			"Writes its files into the module's app, so the app ships it. It stops being custom; that cannot be undone here."
		);
	if (props.custom) return __("Only the module changes: a custom DocType has no files.");
	return __("Its folder moves to the module's app, with its code.");
});

onMounted(async () => {
	try {
		const { data } = await listDocuments<{ name: string; app_name: string }>("Module Def", {
			fields: ["name", "app_name"],
			filters: appModules ? { custom: 0 } : {},
			order_by: "name asc",
			limit: 1000,
		});
		modules.value = data
			// Made standard, it may stay in its module; moved, it leaves it.
			.filter(({ name }) => props.standard || name !== props.module)
			.map(({ name, app_name }) => ({ label: name, value: name, description: app_name }));
	} catch (error) {
		toast.error(errorMessage(error));
	}
});
</script>
