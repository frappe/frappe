<template>
	<!-- Nothing to edit yet, so the pane teaches instead (ticket 37). 23's
	     read-only example is gone from here: it rendered as a full-pane
	     syntax-coloured editor with an active-line highlight, visually identical
	     to a script you could type into, and the only thing saying otherwise was
	     one grey sentence below the fold. That was 23's own reasoning — "it looks
	     like the thing it teaches" — succeeding too well. The example survives
	     where it cannot be mistaken for the editor: the reference.

	     No rail either: a list with nothing in it explains nothing (23). The
	     doctype still has a home in all three states, because the header's trail
	     carries it. -->
	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
		<div class="m-auto w-full max-w-xl">
			<p class="text-base font-semibold text-ink-gray-8">
				Nothing customizes {{ dt }} record pages yet
			</p>
			<p class="mt-1 text-p-sm text-ink-gray-5">
				Start from one of these, or from an empty script.
			</p>

			<!-- Three things a script can *do*, each a starting point that creates a
			     script already using that verb. The fastest path to a real script is
			     not a blank one, and a verb is learned by running it rather than by
			     reading that it exists. -->
			<div class="mt-4 flex flex-col gap-2">
				<button
					v-for="starter in STARTERS"
					:key="starter.label"
					type="button"
					class="flex items-start gap-3 rounded-lg border border-outline-gray-2 p-3 text-left transition hover:border-outline-gray-3 hover:bg-surface-gray-1"
					:disabled="busy"
					@click="emit('create', starter.script)"
				>
					<span
						class="mt-0.5 size-4 shrink-0 text-ink-gray-6"
						:class="starter.icon"
						aria-hidden="true"
					/>
					<span class="min-w-0">
						<span class="block text-p-sm font-medium text-ink-gray-8">
							{{ starter.label }}
						</span>
						<span class="mt-0.5 block font-mono text-p-xs text-ink-gray-5">
							{{ starter.code }}
						</span>
					</span>
				</button>
			</div>

			<!-- Quiet, because they are the two paths the starters exist to make
			     unnecessary — not because they are second-class. -->
			<div class="mt-3 flex items-center gap-4">
				<button
					type="button"
					class="text-p-xs text-ink-gray-5 underline underline-offset-2 hover:text-ink-gray-7"
					:disabled="busy"
					@click="emit('create')"
				>
					Start from an empty script
				</button>
				<button
					type="button"
					class="text-p-xs text-ink-gray-5 underline underline-offset-2 hover:text-ink-gray-7"
					@click="emit('reference')"
				>
					Open the reference
				</button>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
// The zero-scripts layout: one of three, because the same layout lied about two
// of them (ticket 23). This one owns its own primary action — there is no rail
// and no footer for it to live in.
defineProps<{
	/** The doctype whose record pages nothing customizes yet. */
	dt: string;
	/** A write is in flight; the state stays readable but starts nothing new. */
	busy?: boolean;
}>();

const emit = defineEmits<{
	/**
	 * Create a script opening with this body. Omitted, the doctype's own
	 * default prefills — which is what "start from an empty script" means.
	 */
	create: [script?: string];
	reference: [];
}>();

// Each starter's body is a working script for its verb, so what the author
// lands in already runs. They are deliberately short: the reference is one
// click away and holds the rest.
const STARTERS = [
	{
		label: "Add a quick action to the header",
		code: "page.quickActions.add({ label, onClick })",
		icon: "lucide-mouse-pointer-click",
		script: `export default {
  refresh(page) {
    page.quickActions.add({
      label: 'Renew',
      onClick: () => page.toast.success('Renewed'),
    })
  },
}`,
	},
	{
		label: "Open a dialog from a button",
		code: "page.dialog.open({ title, doctype, fieldnames })",
		icon: "lucide-square-arrow-out-up-right",
		script: `export default {
  refresh(page) {
    page.quickActions.add({
      label: 'Log a call',
      onClick: () =>
        page.dialog.open({
          title: 'Log a call',
          doctype: page.doc.doctype,
          fieldnames: ['status'],
        }),
    })
  },
}`,
	},
	// Role-gating is a plain `if` over `page.roles` rather than a `roles` option
	// on a verb — the decision ticket 18 made, and the reason `page` has no
	// `condition` anywhere. There is no field-level verb: fields live inside
	// panel sections, so hiding is done at the section (`panelSections.hide`).
	{
		label: "Show a section to some roles only",
		code: "if (!page.roles.includes(…)) page.panelSections.hide(…)",
		icon: "lucide-eye-off",
		script: `export default {
  refresh(page) {
    // Hiding is not enforcement — the server still decides who may read it.
    if (!page.roles.includes('Sales Manager')) {
      page.panelSections.hide('financials')
    }
  },
}`,
	},
];
</script>
