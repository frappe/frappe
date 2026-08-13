<template>
	<!-- The editor as a dialog, so a script author can stay on the record they
	     are customizing and watch it replay behind it. The accepted cost, measured
	     rather than assumed (ticket 23): Dialog's focus trap leaves that record
	     visible but unclickable while the editor is open.

	     `bare` is the SettingsDialog pattern — Dialog owns the overlay, focus trap
	     and escape; the panel owns its geometry. Width still passes through
	     Dialog's `size` (a max-w-* cap), so `7xl` is as wide as it goes; the panel
	     takes all of it, and owns the height Dialog never sets.

	     The height is `100vh` less Dialog's own vertical padding, not a share of
	     the viewport: the panel does not own the screen it is measured against.
	     Dialog centres it in a scrollable `fixed inset-0` overlay whose track is
	     `min-h-screen` and which spends 6rem on the panel's behalf — `py-4` on the
	     centring track plus `my-8` on the content — so any `Nvh` tall enough to be
	     worth having overflows that track and scrolls the screen behind the focus
	     trap. 23's `92vh` did, by 24px at 900px tall, and no single percentage can
	     avoid it: 6rem is a shrinking share of a growing viewport. Removing the
	     overlay's padding is the other fix and is not ours to make — it is what
	     keeps a panel off the screen edge everywhere else. -->
	<Dialog v-model="isOpen" bare size="7xl">
		<div
			class="flex h-[calc(100vh-6rem)] w-full flex-col overflow-hidden rounded-xl bg-surface-elevation-1"
		>
			<PageScriptEditor
				v-model:script="script"
				:dt="dt"
				:replaysOn="replaysOn"
				:onClose="close"
			/>
		</div>
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog } from "frappe-ui";
import PageScriptEditor from "./PageScriptEditor.vue";

defineProps<{
	dt: string;
	/** The record the editor is opened over, named in its saved-state line. */
	replaysOn?: string;
}>();

const isOpen = defineModel<boolean>({ default: false });

/** Passed through to the pane, which owns the fallback when it is stale. */
const script = defineModel<string | undefined>("script", { default: undefined });

function close() {
	isOpen.value = false;
}
</script>
