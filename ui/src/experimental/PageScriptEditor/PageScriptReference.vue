<template>
	<!-- The standing explanations, findable once and out of the way after
	     (ticket 23). It covers the editor rather than sitting beside it: it is
	     read on the first visit and on no other. -->
	<div
		class="absolute inset-0 flex flex-col gap-3 overflow-y-auto bg-surface-elevation-1 p-5"
		role="dialog"
		aria-label="Page script reference"
	>
		<div class="flex items-center">
			<span class="text-p-base font-semibold text-ink-gray-8">Reference</span>
			<Button
				class="ml-auto"
				variant="ghost"
				icon="lucide-x"
				label="Close reference"
				@click="emit('close')"
			/>
		</div>
		<dl class="grid grid-cols-[7rem_1fr] gap-x-4 gap-y-2 text-p-sm">
			<dt class="text-ink-gray-5">Order</dt>
			<dd class="text-ink-gray-7">
				Top to bottom; the last script to run wins. Drag to reorder.
			</dd>
			<dt class="text-ink-gray-5">Imports</dt>
			<dd class="text-ink-gray-7">{{ SHARED_DEPS.join(" · ") }}</dd>
			<dt class="text-ink-gray-5">Handlers</dt>
			<dd class="text-ink-gray-7">refresh · before_save · &lt;fieldname&gt;</dd>
			<dt class="text-ink-gray-5">page</dt>
			<dd class="text-ink-gray-7">
				quickActions · headerActions · tabs · panelSections · dialog · doc · perms · roles
				· fieldAccess
			</dd>
			<dt class="text-ink-gray-5">Permissions</dt>
			<dd class="text-ink-gray-7">
				Anything a script hides is hidden from the eye, not from the server. A user who
				can't see the button can still make the call.
			</dd>
			<dt class="text-ink-gray-5">Compatibility</dt>
			<dd class="text-ink-gray-7">
				What <code>page</code> intends to keep, and what it explicitly does not
				promise, is written in <code>@framework/ui</code>'s
				<code>src/experimental/RecordPage/COMPATIBILITY.md</code>.
			</dd>
			<dt class="text-ink-gray-5">Errors</dt>
			<dd class="text-ink-gray-7">
				What a script puts in an error message may be stored in this site's Error Log.
			</dd>
		</dl>
		<p class="text-p-sm font-medium text-ink-gray-7">Example</p>
		<pre
			class="whitespace-pre-wrap rounded-lg bg-surface-gray-2 px-4 py-3 text-p-sm leading-6 text-ink-gray-7"
			>{{ EXAMPLE_SCRIPT }}</pre>
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { SHARED_DEPS } from "./importLint";
import { EXAMPLE_SCRIPT } from "./exampleScript";

const emit = defineEmits<{ close: [] }>();
</script>
