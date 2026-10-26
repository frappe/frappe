<!-- The settings dialog at `#settings/<prefix>/<pane>/<block>`. A short address is replaced by
     the full one; one that cannot be shown keeps its hash and shows one message. -->
<template>
	<SettingsDialog v-model:open="open" v-model:tab="tab" size="5xl" :keyboard-shortcut="false">
		<SettingsSidebar>
			<SettingsNavGroup
				v-for="group in groups"
				:key="group.prefix"
				:label="group.label"
				:data-group="group.prefix"
			>
				<SettingsNavItem
					v-for="pane in group.panes"
					:key="pane.key"
					:value="`${group.prefix}/${pane.key}`"
				>
					<template #prefix>
						<Avatar
							v-if="pane.app === FRAMEWORK && pane.key === 'profile'"
							size="xs"
							:label="boot.session.user.full_name"
							:image="boot.session.user.user_image"
						/>
						<Icon v-else :name="pane.icon" class="text-ink-gray-6" />
					</template>
					{{ __(pane.label) }}
				</SettingsNavItem>
			</SettingsNavGroup>
			<div v-if="!book && !failed" class="flex flex-col gap-0.5" aria-hidden="true">
				<div v-for="row in 3" :key="row" class="flex h-7 items-center gap-2 px-2">
					<Skeleton class="size-4 rounded-2" />
					<Skeleton class="h-3.5 w-24 rounded-1" />
				</div>
			</div>
		</SettingsSidebar>
		<SettingsContent>
			<template v-for="group in groups" :key="group.prefix">
				<SettingsPanel
					v-for="pane in group.panes"
					:key="pane.key"
					:value="`${group.prefix}/${pane.key}`"
					class="relative min-w-0"
				>
					<SettingsPaneView :pane="pane" :blocks="blocks!" :block="shown?.block" />
				</SettingsPanel>
			</template>
			<div
				v-if="failed || refused"
				role="status"
				class="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center"
			>
				<p class="text-base text-ink-gray-6">
					{{
						failed
							? __("Settings could not load.")
							: __("This settings pane does not exist, or you cannot see it")
					}}
				</p>
				<Button v-if="failed" :label="__('Try again')" @click="load" />
			</div>
		</SettingsContent>
	</SettingsDialog>
</template>

<script setup lang="ts">
import { computed, inject, ref, shallowRef, watch, type Component } from "vue";
import {
	Avatar,
	Button,
	SettingsContent,
	SettingsDialog,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsPanel,
	SettingsSidebar,
	Skeleton,
} from "frappe-ui";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import Icon from "@/icons/Icon.vue";
import { useHashDialog } from "./useHashDialog";
import { FRAMEWORK, SettingsAddressBook } from "./settingsAddress";
import { loadSettingsBlocks } from "./settingsBlocks";
import { fetchPanes } from "./settingsPanes";
import SettingsPaneView from "./SettingsPaneView.vue";

const boot = inject<Boot>("boot")!;
const hash = useHashDialog("settings");

const book = shallowRef<SettingsAddressBook | null>(null);
const blocks = shallowRef<Component>();
const failed = ref(false);

function load() {
	failed.value = false;
	Promise.all([fetchPanes(boot), loadSettingsBlocks()]).then(
		([reply, component]) => {
			blocks.value = component;
			book.value = new SettingsAddressBook(reply, boot);
		},
		() => (failed.value = true)
	);
}
load();

const resolution = computed(() =>
	hash.open.value ? book.value?.resolve(hash.segments.value) : undefined
);
const shown = computed(() =>
	resolution.value && !("refused" in resolution.value) ? resolution.value : undefined
);
const refused = computed(() => !!resolution.value && "refused" in resolution.value);

// A foreign app's group lists from the address that showed it until the dialog closes.
const visiting = ref<string>();
watch(
	shown,
	(address) => {
		if (address?.rewrite) hash.write(...address.rewrite);
		else if (address && book.value?.isForeign(address.prefix)) visiting.value = address.prefix;
	},
	{ immediate: true }
);
watch(hash.open, (isOpen) => isOpen || (visiting.value = undefined));

const groups = computed(() => book.value?.groups(visiting.value) ?? []);

const open = computed({
	get: () => hash.open.value,
	set: (value) => (value ? hash.write() : hash.close()),
});

// Never undefined: reka's tabs read an undefined first value as uncontrolled and would switch
// panes before the hash moves, past the blocks' leave question.
const tab = computed({
	get: () => (shown.value ? `${shown.value.prefix}/${shown.value.pane.key}` : ""),
	set: (value) => value && hash.write(...String(value).split("/")),
});
</script>
