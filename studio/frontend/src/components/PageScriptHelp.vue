<template>
	<div class="text-sm leading-relaxed text-ink-gray-5">
		<p>
			A page script is a TypeScript module. Import what you use, and return the values and handlers
			this page's bindings and events need.
		</p>
		<ul class="my-2 list-disc space-y-0.5 pl-4">
			<li>
				Export a default
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">setup(context)</code>
				function.
			</li>
			<li>
				Import from
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">vue</code>
				,
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">frappe-ui</code>
				, or this app's own files with
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">@app/…</code>
				.
			</li>
			<li>
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">context</code>
				holds this page's data sources and variables, plus
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">route</code>
				and
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">router</code>
				.
			</li>
			<li>Only what you return is available to props and events.</li>
		</ul>
		<pre class="overflow-x-auto rounded-4 bg-surface-gray-2 p-2 text-xs leading-snug text-ink-gray-7">
import { ref, computed } from "vue"

export default function setup(context) {
  const count = ref(0)
  const doubled = computed(() => count.value * 2)
  const rows = computed(() => context.todos.data || [])

  return { count, doubled, rows }
}</pre
		>
		<p class="mt-2">
			Reference them in props, e.g.
			<code v-pre class="rounded-4 bg-surface-gray-2 px-1 text-xs">{{ count }}</code>
			.
		</p>
	</div>
</template>
