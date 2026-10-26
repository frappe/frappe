<!-- A pane's blocks, which the shell's settings dialog mounts: generated rows over each binding's draft,
     each component block's own file, and a floating Save bar while a `button` block holds changes. -->
<template>
	<div ref="root" class="contents">
		<SettingsBody>
			<LoadingStatus v-if="loading" />
			<section
				v-for="block in blocks"
				:key="block.key"
				:data-block="block.key"
				class="relative isolate mt-8 scroll-mt-5 first-of-type:mt-5"
			>
				<span data-flash aria-hidden="true" :class="FLASH" />
				<h3 v-if="block.label" class="text-base font-semibold text-ink-gray-8">
					{{ __(block.label) }}
				</h3>
				<p v-if="block.description" class="mt-0.5 text-sm text-ink-gray-5">
					{{ __(block.description) }}
				</p>
				<SettingsBlockRows
					v-if="drafts.bound.has(block.key)"
					:bound="drafts.bound.get(block.key)!"
					:reveal="reveal?.block === block.key ? reveal : undefined"
					@commit="drafts.commit(drafts.bound.get(block.key)!)"
				/>
				<component
					:is="components.get(block.key)"
					v-else
					:bindings="drafts.components.get(block.key) ?? {}"
				/>
			</section>
			<div v-if="drafts.hasButtons" class="h-16" aria-hidden="true" />
		</SettingsBody>
		<Transition
			enter-from-class="translate-y-3 opacity-0"
			leave-to-class="translate-y-3 opacity-0"
			enter-active-class="transition duration-150"
			leave-active-class="transition duration-150"
		>
			<div
				v-if="drafts.unsavedCount.value || drafts.failedCount.value"
				role="status"
				class="absolute bottom-6 right-6 z-10 flex items-center gap-3 rounded-4 border border-outline-gray-2 bg-surface-elevation-3 py-2 pl-4 pr-2 shadow-xl"
			>
				<span
					class="text-base"
					:class="drafts.failedCount.value ? 'text-ink-red-7' : 'text-ink-gray-7'"
				>
					{{ barText }}
				</span>
				<Button :label="__('Discard')" variant="ghost" @click="drafts.discardButtons()" />
				<Button
					:label="__('Save')"
					variant="solid"
					:loading="drafts.saving.value"
					@click="drafts.saveButtons()"
				/>
			</div>
		</Transition>
	</div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, h, inject, onUnmounted, ref, type Component } from "vue";
import { useRouter } from "vue-router";
import { Button, dialog, SettingsBody } from "frappe-ui";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { settingsComponentFor } from "@/contributions/registry";
import LoadingStatus from "@/shell/LoadingStatus.vue";
import type { SettingsPane } from "@/shell/settingsPanes";
import { discardChanges, type Confirm } from "../record/discardChanges";
import { useSaveKeys } from "../record/recordSave";
import { PaneDrafts } from "./paneDrafts";
import SettingsBlockRows from "./SettingsBlockRows.vue";
import SettingsRowsSkeleton from "./SettingsRowsSkeleton.vue";

const props = defineProps<{
	pane: SettingsPane;
	reveal?: { block: string; fieldname?: string };
}>();
const emit = defineEmits<{ loaded: [] }>();

/** A rounded gray layer a little wider than the block, behind its content. */
const FLASH =
	"pointer-events-none absolute -inset-x-3 -inset-y-2 -z-10 rounded-4 bg-surface-gray-3 opacity-0";

const components = componentsOf(props.pane);
const blocks = props.pane.blocks.filter((block) => !block.component || components.has(block.key));
const boot = inject<Boot>("boot")!;
const drafts = new PaneDrafts({ ...props.pane, blocks }, boot.session.user.name, confirm);
const loading = ref(true);
drafts.loaded.then(() => {
	loading.value = false;
	emit("loaded");
});

const barText = computed(() => {
	const failed = drafts.failedCount.value;
	const unsaved = drafts.unsavedCount.value;
	if (failed)
		return failed === 1 ? __("1 block did not save") : __("{0} blocks did not save", [failed]);
	return unsaved === 1 ? __("1 unsaved change") : __("{0} unsaved changes", [unsaved]);
});

const root = ref<HTMLElement | null>(null);
useSaveKeys({
	save: () => void drafts.saveButtons(),
	unsaved: () => drafts.unsaved(),
	dialog: () => root.value?.closest('[role="dialog"]'),
});

// A pane switch, Back, Esc and a route change all move the address; a typed value is committed first.
const router = useRouter();
const stopGuard = router.beforeEach((to, from) => {
	if (to.path === from.path && paneOf(to.hash) === paneOf(from.hash)) return true;
	(document.activeElement as HTMLElement | null)?.blur?.();
	if (!drafts.unsaved()) return true;
	return discardChanges(confirm, __("This pane has changes that are not saved."));
});
onUnmounted(() => {
	stopGuard();
	drafts.close();
});

/** Each component block's file, loaded when the pane opens; a block whose file is missing is dropped. */
function componentsOf(pane: SettingsPane): Map<string, Component> {
	const components = new Map<string, Component>();
	for (const block of pane.blocks) {
		const loader = block.component && settingsComponentFor(block.app, block.component);
		if (!loader) continue;
		const component = defineAsyncComponent({
			loader: loader as () => Promise<Component>,
			loadingComponent: { render: () => h(SettingsRowsSkeleton, { rows: 3 }) },
			errorComponent: {
				render: () =>
					h(
						"p",
						{ class: "py-3.5 text-base text-ink-red-7" },
						__("This block could not load")
					),
			},
		});
		components.set(block.key, component);
	}
	return components;
}

function paneOf(hash: string): string {
	return hash.split("/").slice(0, 3).join("/");
}

function confirm({ title, message, confirmLabel, cancelLabel }: Parameters<Confirm>[0]) {
	return new Promise<true | null>((resolve) =>
		dialog.confirm({
			title,
			message,
			confirmLabel,
			cancelLabel,
			onConfirm: () => resolve(true),
			onCancel: () => resolve(null),
		})
	);
}
</script>
