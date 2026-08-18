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
	     keeps a panel off the screen edge everywhere else.

	     The header's `×` is back after 37 dropped it, so this owns four ways out:
	     the button, Escape, the overlay and Back (the hash route, tickets 31/32).
	     Dialog already owned the last three; what the button adds is one that is
	     visible. -->
	<Dialog v-model="isOpen" bare size="7xl">
		<div
			class="flex h-[calc(100vh-6rem)] w-full flex-col overflow-hidden rounded-xl bg-surface-elevation-1"
		>
			<!-- `bare` renders this slot straight into reka's `DialogContent` and no
			     `DialogTitle` with it — but reka still points the content's
			     `aria-labelledby`/`aria-describedby` at the ids a title and a
			     description *would* have owned. Nothing owns them, so the references
			     dangle and the dialog computes to the empty name (ticket 38). These
			     two elements are what own those ids.

			     `sr-only`, duplicating the pane's visible header, rather than wrapping
			     that header in `Dialog.Title as-child`: the name is the dialog's, the
			     header is the pane's, and the pane stayed free to restyle it (ticket
			     39 did) without silently renaming the dialog or acquiring a hard
			     requirement for a Dialog ancestor. It is the pattern frappe-ui's own
			     SettingsDialog uses. -->
			<Dialog.Title as-child>
				<h1 class="sr-only">Page scripts · {{ dt }}</h1>
			</Dialog.Title>
			<Dialog.Description as-child>
				<p class="sr-only">
					Write and order the scripts that customize {{ dt }} record pages. They replay
					on the record behind this dialog as you save.
				</p>
			</Dialog.Description>

			<PageScriptEditor
				v-model:dt="dt"
				v-model:script="script"
				:replaysOn="replaysOn"
				:record="record"
				:onClose="close"
			/>
		</div>
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog } from "frappe-ui";
import PageScriptEditor from "./PageScriptEditor.vue";

defineProps<{
	/** The record a save replays on, absent when it is not this doctype's. */
	replaysOn?: string;
	/**
	 * The record behind the dialog whatever its doctype — what lets the pane
	 * withdraw the replay claim out loud after the doctype crumb is switched.
	 */
	record?: string;
}>();

const isOpen = defineModel<boolean>({ default: false });

/**
 * The doctype being edited. A model because the header's doctype crumb switches
 * it, and the host is what turns that into `#page-scripts/<doctype>`.
 */
const dt = defineModel<string>("dt", { required: true });

/** Passed through to the pane, which owns the fallback when it is stale. */
const script = defineModel<string | undefined>("script", { default: undefined });

function close() {
	isOpen.value = false;
}
</script>
