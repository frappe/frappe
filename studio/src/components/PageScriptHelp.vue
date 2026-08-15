<template>
	<div class="text-sm leading-relaxed text-ink-gray-5">
		<p>
			Write this page's logic like a Vue
			<code class="rounded bg-surface-gray-2 px-1 text-xs">&lt;script setup&gt;</code>
			. Anything you declare is exposed to this page's bindings and events.
		</p>
		<ul class="my-2 list-disc space-y-0.5 pl-4">
			<li>
				Reactive state with
				<code class="rounded bg-surface-gray-2 px-1 text-xs">ref</code>
				/
				<code class="rounded bg-surface-gray-2 px-1 text-xs">reactive</code>
				, derived values with
				<code class="rounded bg-surface-gray-2 px-1 text-xs">computed</code>
				, side effects with
				<code class="rounded bg-surface-gray-2 px-1 text-xs">watch</code>
				.
			</li>
			<li>Functions to wire to component events (e.g. a button's click).</li>
			<li>Read this page's variables, data sources and attached modules directly by name.</li>
		</ul>
		<pre class="overflow-x-auto rounded bg-surface-gray-2 p-2 text-xs leading-snug text-ink-gray-7">
const count = ref(0)
const doubled = computed(() => count.value * 2)

function increment() {
  count.value++
}</pre
		>
		<p class="mt-2">
			Reference them in props, e.g.
			<code v-pre class="rounded bg-surface-gray-2 px-1 text-xs">{{ count }}</code>
			.
		</p>
	</div>
</template>
