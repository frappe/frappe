<!--
  The chrome of a navigation that no rail draws: the app's logo and title as one button that opens
  the app menu, with the utility slots as rows under it.
-->
<template>
	<div class="shrink-0">
		<div class="flex h-12 items-center px-2">
			<Dropdown :options="menu" align="start">
				<button
					type="button"
					data-key="app-menu"
					class="flex h-8 min-w-0 items-center gap-2 rounded-4 px-2 transition hover:bg-surface-gray-3 focus-visible:ring-0 focus-visible:focus-ring"
					:aria-label="__('{0} menu', [appTitle])"
					@pointerenter="loadApps"
					@focus="loadApps"
				>
					<img
						v-if="boot.app_logo"
						:src="boot.app_logo"
						alt=""
						class="size-6 rounded-3"
					/>
					<span
						v-else
						class="flex size-6 shrink-0 items-center justify-center rounded-3 bg-surface-gray-3 text-sm font-medium text-ink-gray-8"
						aria-hidden="true"
						>{{ appTitle.charAt(0).toUpperCase() }}</span
					>
					<span class="truncate text-base font-medium text-ink-gray-8">{{
						appTitle
					}}</span>
					<span
						class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5"
						aria-hidden="true"
					/>
				</button>
			</Dropdown>
		</div>
		<div class="flex flex-col gap-0.5 px-2 pb-2">
			<UtilitySlots form="row" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Dropdown } from "frappe-ui";
import { __ } from "@/i18n";
import { useAppMenu } from "./appMenu";
import UtilitySlots from "./UtilitySlots.vue";

const { boot, appTitle, menu, loadApps } = useAppMenu();
</script>
