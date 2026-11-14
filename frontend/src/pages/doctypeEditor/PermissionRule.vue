<!-- One permission rule: its role and badges, a box per column right, "More" for the rest, and a
     menu to remove it. -->
<template>
	<tr
		class="border-t border-outline-gray-1"
		:data-perm-role="rule.role"
		:data-perm-level="rule.permlevel"
	>
		<td class="px-3 py-1.5">
			<div class="flex min-w-0 items-center gap-2">
				<span class="truncate text-ink-gray-8">{{ rule.role }}</span>
				<Badge
					v-if="rule.permlevel"
					:label="__('Level {0}', [String(rule.permlevel)])"
					theme="gray"
					size="sm"
					class="shrink-0"
				/>
				<Tooltip
					v-if="rule.if_owner"
					:text="__('Only the records this role\'s people created.')"
				>
					<Badge
						:label="__('Only if creator')"
						theme="gray"
						size="sm"
						class="shrink-0"
					/>
				</Tooltip>
			</div>
		</td>
		<td v-for="right in shown" :key="right" class="px-1 py-1.5">
			<div class="flex justify-center">
				<Tooltip :text="refusal(right)" :disabled="!refusal(right)">
					<span class="inline-flex">
						<Checkbox
							:model-value="Boolean(rule[right])"
							:disabled="Boolean(refusal(right))"
							:aria-label="`${rule.role}: ${__(RIGHT_LABELS[right])}`"
							:data-perm-right="right"
							@update:model-value="toggle(right, Boolean($event))"
						/>
					</span>
				</Tooltip>
			</div>
		</td>
		<td class="px-1 py-1.5 text-center">
			<!-- A rule above level 0 only reads and writes its fields: no more rights to give. -->
			<span
				v-if="rule.permlevel"
				class="text-ink-gray-5"
				:aria-label="__('No more rights at this level')"
				>—</span
			>
			<Popover v-else side="bottom" align="end">
				<template #trigger>
					<Button
						variant="ghost"
						size="sm"
						:label="moreLabel"
						:icon="moreLabel ? undefined : 'lucide-plus'"
						:aria-label="__('More rights for {0}', [rule.role])"
						data-perm-more
					/>
				</template>
				<div class="flex w-[200px] flex-col p-1" data-perm-more-popover>
					<p class="px-1.5 py-1 text-sm text-ink-gray-6">{{ rule.role }}</p>
					<Checkbox
						v-for="right in more"
						:key="right"
						padded
						:title="RIGHT_HELP[right] ? __(RIGHT_HELP[right]) : undefined"
						:label="__(RIGHT_LABELS[right])"
						:description="refusal(right) || undefined"
						:disabled="Boolean(refusal(right))"
						:model-value="Boolean(rule[right])"
						:data-perm-right="right"
						@update:model-value="toggle(right, Boolean($event))"
					/>
					<Checkbox
						v-if="creator"
						padded
						:title="__('Only the records this role\'s people created.')"
						:label="__('Only if creator')"
						:description="creatorRefusal || undefined"
						:disabled="Boolean(creatorRefusal)"
						:model-value="Boolean(rule.if_owner)"
						data-perm-if-owner
						@update:model-value="
							view.permission('set_if_owner', { ...key, value: $event ? 1 : 0 })
						"
					/>
				</div>
			</Popover>
		</td>
		<td class="py-1.5 pr-1.5 text-right">
			<Dropdown :options="menu" side="bottom" align="end">
				<Button
					variant="ghost"
					size="sm"
					icon="lucide-ellipsis"
					:aria-label="__('Actions for {0}', [rule.role])"
				/>
			</Dropdown>
		</td>
	</tr>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Badge, Button, Checkbox, Dropdown, Popover, Tooltip } from "frappe-ui";
import { __ } from "@/i18n";
import { RIGHT_HELP, RIGHT_LABELS, rightRefusal } from "./permissionColumns";
import type { PermissionRow, Right } from "./settingsModel";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{
	rule: PermissionRow;
	shown: Right[];
	more: Right[];
	creator: boolean;
	last: boolean;
}>();
const view = inject(SettingsViewKey)!;

const key = computed(() => ({
	role: props.rule.role,
	permlevel: props.rule.permlevel,
	if_owner: props.rule.if_owner,
}));
const moreLabel = computed(() => {
	const on = props.more.filter((right) => props.rule[right]).length + props.rule.if_owner;
	return on ? `+${on}` : "";
});
// Only if creator is part of the rule's key: a twin rule with the other value blocks the move.
const creatorRefusal = computed(() => {
	if (props.rule.permlevel && !props.rule.if_owner)
		return __("Only if creator is for level 0 rules.");
	const twin = view.settings.permissions.some(
		(one) =>
			one.role === props.rule.role &&
			one.permlevel === props.rule.permlevel &&
			one.if_owner !== props.rule.if_owner
	);
	return twin ? __("{0} already has that rule.", [props.rule.role]) : "";
});
const menu = computed(() => [
	{
		label: __("Remove"),
		icon: "lucide-trash-2",
		disabled: props.last,
		onClick: () => view.permission("remove_permission", key.value),
	},
]);

const refusal = (right: Right) =>
	rightRefusal(props.rule, right, Boolean(Number(view.value("allow_import"))));
const toggle = (right: Right, value: boolean) =>
	view.permission("set_permission", { ...key.value, right, value: value ? 1 : 0 });
</script>
