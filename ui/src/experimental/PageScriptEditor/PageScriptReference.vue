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
			<dd class="text-ink-gray-7">
				refresh · before_save (a throw aborts the save) · after_save · on_tab_change ·
				&lt;fieldname&gt; · &lt;tablefield&gt;_add · &lt;tablefield&gt;_remove
			</dd>
			<dt class="text-ink-gray-5">Surfaces</dt>
			<dd class="text-ink-gray-7">
				quickActions · headerActions · tabs · panelSections — each with
				<code>add</code>, <code>hide</code>, <code>show</code>, <code>update</code>,
				<code>move</code>, <code>has</code>, <code>order</code>. An added item needs a
				<code>name</code>, and its callback is <code>run</code>.
			</dd>
			<dt class="text-ink-gray-5">page</dt>
			<dd class="text-ink-gray-7">
				doctype · docname · doc · meta · isDirty · perms · roles · fieldAccess · dialog ·
				toast · call · router · save · reload · refresh
			</dd>
			<dt class="text-ink-gray-5">Icons</dt>
			<dd class="text-ink-gray-7">
				An <code>icon</code> is a <code>lucide-*</code> name, and only names this site's
				pages already use will render — an unknown one warns in the console and draws
				nothing.
			</dd>
			<dt class="text-ink-gray-5">Permissions</dt>
			<dd class="text-ink-gray-7">
				Anything a script hides is hidden from the eye, not from the server. A user who
				can't see the button can still make the call.
			</dd>
			<dt class="text-ink-gray-5">Compatibility</dt>
			<dd class="text-ink-gray-7">
				What <code>page</code> intends to keep, and what it explicitly does not promise, is
				written in <code>@framework/ui</code>'s
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
