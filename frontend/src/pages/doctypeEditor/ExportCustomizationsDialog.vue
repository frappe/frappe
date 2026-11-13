<!-- Export customizations (developer mode): what desk v1's export asks. It closes with the answers. -->
<template>
	<div class="flex flex-col gap-5" data-export-dialog>
		<p class="text-p-base text-ink-gray-7">
			{{
				__(
					"Writes this site's changes to {0} into an app, so every site with the app gets them.",
					[doctype]
				)
			}}
		</p>
		<Combobox
			v-model="module"
			:label="__('Module')"
			:options="modules"
			:placeholder="__('Choose a module')"
		/>
		<div class="flex items-start justify-between gap-4">
			<div class="flex flex-col gap-0.5">
				<span class="text-base text-ink-gray-8">{{ __("Apply on migrate") }}</span>
				<span class="text-sm text-ink-gray-5">
					{{ __("Each migrate writes them to the site again.") }}
				</span>
			</div>
			<Switch v-model="sync" />
		</div>
		<div class="flex items-start justify-between gap-4">
			<div class="flex flex-col gap-0.5">
				<span class="text-base text-ink-gray-8">{{ __("Include permissions") }}</span>
				<span class="text-sm text-ink-gray-5">
					{{ __("The roles this site added to {0}.", [doctype]) }}
				</span>
			</div>
			<Switch v-model="permissions" />
		</div>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button variant="solid" :label="__('Export')" :disabled="!module" @click="exportNow" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Button, Combobox, Switch } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { __ } from "@/i18n";
import type { ExportAnswers } from "./customizeActs";

const props = defineProps<{
	doctype: string;
	/** The DocType's own module, picked first. */
	module: string;
	close: (answers: ExportAnswers | null) => void;
}>();

const module = ref<string | null>(props.module);
const modules = ref<string[]>([props.module]);
const sync = ref(true);
const permissions = ref(false);

onMounted(async () => {
	const { data } = await listDocuments<{ name: string }>("Module Def", {
		fields: ["name"],
		order_by: "name asc",
		limit: 1000,
	});
	modules.value = data.map(({ name }) => name);
});

function exportNow() {
	props.close({
		module: module.value!,
		sync_on_migrate: sync.value,
		with_permissions: permissions.value,
	});
}
</script>
