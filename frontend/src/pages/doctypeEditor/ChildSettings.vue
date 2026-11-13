<!-- A child table's Settings tab: how its grid edits rows. Each switch stages a DocType setting on
     the child, which saves with the parent. -->
<template>
	<div class="mx-auto flex w-full max-w-3xl flex-col py-6" data-child-settings>
		<div
			class="flex flex-col divide-y divide-outline-gray-1 rounded-6 border border-outline-gray-1"
		>
			<label
				v-for="setting in SETTINGS"
				:key="setting.property"
				class="flex items-center justify-between gap-4 px-4 py-3"
			>
				<span class="flex flex-col gap-0.5">
					<span class="text-base font-medium text-ink-gray-8">{{
						__(setting.label)
					}}</span>
					<span class="text-p-sm text-ink-gray-5">{{ __(setting.description) }}</span>
				</span>
				<Switch
					size="sm"
					:model-value="session.edits.setting(session.state, setting.property)"
					:disabled="!session.canvas.editable"
					:data-child-setting="setting.property"
					@update:model-value="set(setting.property, $event)"
				/>
			</label>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Switch } from "frappe-ui";
import { __ } from "@/i18n";
import type { ChildSession } from "./childTables";

const props = defineProps<{ session: ChildSession }>();

const SETTINGS = [
	{
		property: "editable_grid",
		label: "Editable grid",
		description: "Rows are edited in the grid's cells; else each row opens its form.",
	},
	{
		property: "allow_bulk_edit",
		label: "Allow bulk edit",
		description: "The grid offers to download its rows and upload them back.",
	},
] as const;

function set(property: "editable_grid" | "allow_bulk_edit", value: boolean) {
	props.session.edits.stage({
		act: "settings.set_doctype_property",
		value: { property, value: value ? 1 : 0 },
		tab: "settings",
	});
}
</script>
