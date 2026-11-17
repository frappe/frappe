<!--
  The floating bar over the last rows while a saved view has changes: Discard, Save as new and Save.
  It floats where the bulk bar does, in its look, and gives way to it while rows are selected.
-->
<template>
	<div v-if="view.layer" class="relative h-0 shrink-0">
		<!-- Always mounted: a live region that appears with its text is not announced. -->
		<span class="sr-only" role="status">{{
			open ? `${__("Unsaved changes to")} ${host.view().label}` : ""
		}}</span>
		<div
			v-if="open"
			class="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-24 bg-[linear-gradient(to_top,var(--surface-base)_30%,transparent)]"
		/>
		<Transition
			enter-active-class="transition duration-150 ease-out"
			enter-from-class="translate-y-2 opacity-0"
			leave-active-class="transition duration-100 ease-in"
			leave-to-class="translate-y-2 opacity-0"
		>
			<div
				v-if="open"
				class="absolute inset-x-0 bottom-4 z-20 mx-auto w-max max-w-[calc(100%-2rem)]"
			>
				<div
					class="flex h-11 w-max max-w-full items-center rounded-6 bg-surface-base py-2 pe-2 ps-3 text-base shadow-[0_1px_2px_rgb(0_0_0/.06),0_8px_24px_rgb(0_0_0/.12),0_24px_48px_rgb(0_0_0/.1)] ring-1 ring-outline-gray-3"
					role="group"
					:aria-label="__('Unsaved view changes')"
					data-view-save-bar
				>
					<span
						class="me-2 size-1.5 shrink-0 rounded-full bg-surface-gray-7"
						aria-hidden="true"
					/>
					<span class="truncate text-ink-gray-7" :title="host.view().label">
						{{ __("Unsaved changes to") }}
						<span class="font-medium text-ink-gray-9">{{ host.view().label }}</span>
					</span>
					<div
						class="me-1 ms-3 h-4 shrink-0 border-s border-outline-gray-2"
						aria-hidden="true"
					/>
					<div class="flex shrink-0 items-center gap-0.5">
						<Button
							v-if="host.drawn('discard_changes')"
							variant="ghost"
							:label="__('Discard')"
							data-act="list.discard_changes"
							@click="host.run('discard_changes')"
						/>
						<Button
							v-if="host.drawn('save_view_as')"
							:variant="view.saveable.value ? 'ghost' : 'subtle'"
							:label="__('Save as new')"
							data-act="list.save_view_as"
							@click="asking = true"
						/>
						<Tooltip
							v-if="view.saveable.value && host.drawn('save_view')"
							:text="writesTo"
						>
							<Button
								variant="subtle"
								:label="__('Save')"
								:loading="saving"
								data-act="list.save_view"
								@click="save"
							/>
						</Tooltip>
					</div>
				</div>
			</div>
		</Transition>
	</div>
	<!-- The key remounts it per request: a confirmed dialog closes itself but stays mounted. -->
	<ViewDialogs
		v-if="asking"
		:key="asked"
		:request="{ kind: 'save_as_new', view: asView }"
		:run="host.call"
		@close="asking = false"
	/>
</template>

<script setup lang="ts">
import { Button, Tooltip, toast } from "frappe-ui";
import { computed, defineAsyncComponent, ref, watch } from "vue";
import { __ } from "@/i18n";
import type { ListedView } from "@/list/listedViews";
import type { View } from "@/list/view";
import { errorMessage } from "@/recordPage/errorMessage";
import type { SwitcherHost } from "./viewSwitcher/switcherHost";

const ViewDialogs = defineAsyncComponent(() => import("./viewSwitcher/ViewDialogs.vue"));

const props = defineProps<{
	view: View;
	host: SwitcherHost;
	/** True while rows are selected: the bulk bar has the spot. */
	yielding: boolean;
}>();

const open = computed(() => props.host.view().modified && !props.yielding);
const saving = ref(false);
const asking = ref(false);
const asked = ref(0);
watch(asking, (now) => now && asked.value++);

// The dialog names its suggestion from the view's label.
const asView = computed<ListedView>(() => {
	const { key, label, type, layer } = props.host.view();
	return { key, label, type, layer };
});

const WRITES_TO = {
	own: () => __("Saves your view"),
	site: () => __("Saves the view for everyone on the site"),
	app: () => __("Saves for the site, over the app's view"),
};
const writesTo = computed(() => WRITES_TO[props.view.layer ?? "own"]());

async function save() {
	if (saving.value) return;
	saving.value = true;
	try {
		await props.host.call("save_view");
	} catch (error) {
		toast.error(errorMessage(error));
	} finally {
		saving.value = false;
	}
}
</script>
