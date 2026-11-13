<!-- Permissions: a table of roles by rights. A right ticks the rights it needs, and unticking one
     unticks the rights that need it. -->
<template>
	<div
		class="relative flex flex-col gap-3 py-2"
		:data-setting="row.key"
		data-settings-permissions
	>
		<span data-flash aria-hidden="true" :class="FLASH" />
		<div v-if="view.customize" class="flex min-h-7 items-center gap-3">
			<Badge
				:label="site ? __('Site permissions') : __('App permissions')"
				theme="gray"
				data-perm-source
			/>
			<!-- Locked, there is no first change to copy them. -->
			<p class="min-w-0 flex-1 text-p-sm text-ink-gray-5">
				<template v-if="site">
					{{ __("This site's rules replace {0}'s for {1}.", [view.app, view.doctype]) }}
				</template>
				<template v-else-if="!locked">
					{{
						__(
							"{0}'s rules. Your first change copies them, and the site's copy replaces them.",
							[view.app]
						)
					}}
				</template>
			</p>
			<Button
				v-if="site && !locked"
				:label="__('Reset to app permissions')"
				icon-left="lucide-rotate-ccw"
				@click="view.permission('reset_permissions')"
			/>
		</div>
		<p
			v-else-if="view.siteOverridesPermissions"
			class="text-p-sm text-ink-gray-6"
			data-site-override
		>
			{{ __("This site uses its own permissions for {0}.", [view.doctype]) }}
			<RouterLink
				v-if="view.customizeRoute()"
				:to="view.customizeRoute()!"
				class="text-ink-gray-8 underline decoration-outline-gray-3 underline-offset-2 hover:decoration-ink-gray-5"
			>
				{{ __("Edit them in Customize.") }}
			</RouterLink>
		</p>

		<p
			v-if="locked"
			class="flex items-center gap-1.5 text-p-sm text-ink-gray-6"
			data-perm-locked
		>
			<span class="lucide-lock size-3.5 shrink-0 text-ink-gray-4" aria-hidden="true" />
			{{ locked }}
		</p>
		<div
			class="overflow-hidden rounded-6 ring-1 ring-outline-gray-2"
			:class="locked && 'opacity-60'"
			:inert="Boolean(locked)"
		>
			<table class="w-full table-fixed text-base">
				<thead class="bg-surface-gray-1 text-sm text-ink-gray-5">
					<tr>
						<th class="px-3 py-2 text-left font-normal">{{ __("Role") }}</th>
						<th
							v-for="right in shown"
							:key="right"
							class="w-[52px] px-1 py-2 text-center font-normal"
						>
							{{ __(RIGHT_LABELS[right]) }}
						</th>
						<th class="w-14 px-1 py-2 text-center font-normal">{{ __("More") }}</th>
						<th class="w-10" :aria-label="__('Actions')" />
					</tr>
				</thead>
				<tbody>
					<PermissionRule
						v-for="rule in rules"
						:key="ruleKey(rule)"
						:rule="rule"
						:shown="shown"
						:more="more"
						:last="rules.length === 1"
					/>
				</tbody>
			</table>
		</div>
		<ul v-if="errors.length" class="text-p-sm text-ink-red-5" data-setting-errors>
			<li v-for="error in errors" :key="error">{{ error }}</li>
		</ul>
		<Combobox
			v-if="!locked"
			:key="rules.length"
			class="w-[200px]"
			variant="subtle"
			:model-value="''"
			:options="roleOptions"
			:placeholder="__('Add a role')"
			data-perm-add
			@update:model-value="
				$event &&
					view.permission('add_permission', {
						role: String($event),
						permlevel: 0,
						if_owner: 0,
					})
			"
		>
			<template #prefix
				><span class="lucide-plus size-4 text-ink-gray-5" aria-hidden="true"
			/></template>
		</Combobox>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { Badge, Button, Combobox } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { __ } from "@/i18n";
import PermissionRule from "./PermissionRule.vue";
import { RIGHT_LABELS, columns, moreRights } from "./permissionColumns";
import type { PermissionRow } from "./settingsModel";
import type { SettingRow } from "./settingsRows";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{ row: SettingRow }>();
const view = inject(SettingsViewKey)!;

const FLASH =
	"pointer-events-none absolute -inset-x-3 inset-y-0 -z-10 rounded-4 bg-surface-gray-3 opacity-0";

const site = computed(() => view.settings.sitePermissions);
const locked = computed(() => view.settings.permissionsRefusal);
const rules = computed(() => view.settings.permissions);
const shown = computed(() => columns(view.kind));
const more = computed(() => moreRights(view.kind));
const roles = ref<string[]>([]);
const errors = computed(() => view.errors(props.row));

// A role takes one level-0 rule; rules above level 0 come from the Editor's field levels.
const roleOptions = computed(() => {
	const taken = new Set(
		rules.value.filter((rule) => !rule.permlevel && !rule.if_owner).map((rule) => rule.role)
	);
	return roles.value
		.filter((role) => !taken.has(role))
		.map((role) => ({ label: role, value: role }));
});

const ruleKey = (rule: PermissionRow) => `${rule.role}\n${rule.permlevel}\n${rule.if_owner}`;

onMounted(async () => {
	const { data } = await listDocuments<{ name: string }>("Role", {
		fields: ["name"],
		filters: { disabled: 0 },
		order_by: "name asc",
		limit: 500,
	});
	roles.value = data.map((role) => role.name);
});
</script>
