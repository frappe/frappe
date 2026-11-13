<template>
	<div class="text-sm leading-relaxed text-ink-gray-5">
		<p>A component script is a Vue component without a template. The component's blocks are its template.</p>
		<ul class="my-2 list-disc space-y-0.5 pl-4">
			<li>
				Export a default object with
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">props</code>
				,
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">emits</code>
				and
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">setup</code>
				. Each one is optional.
			</li>
			<li>
				The props are the component's inputs. Blocks read them as
				<code v-pre class="rounded-4 bg-surface-gray-2 px-1 text-xs">{{ inputs.title }}</code>
				.
			</li>
			<li>
				A page that uses the component can handle the events in
				<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">emits</code>
				.
			</li>
		</ul>
		<pre class="overflow-x-auto rounded-4 bg-surface-gray-2 p-2 text-xs leading-snug text-ink-gray-7">
import { ref, computed } from "vue"

export default {
  props: {
    title: { type: String, required: true },
    step: { type: Number, default: 1 },
  },
  emits: ["change"],
  setup(props, { emit }) {
    const count = ref(0)
    const label = computed(() => `${props.title}: ${count.value}`)
    function add() {
      count.value += props.step
      emit("change", count.value)
    }
    return { count, label, add }
  },
}</pre
		>
		<p class="mt-2">
			Reference what
			<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">setup</code>
			returns in props and events, e.g.
			<code v-pre class="rounded-4 bg-surface-gray-2 px-1 text-xs">{{ label }}</code>
			or
			<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">add()</code>
			. To choose the control for a prop, add
			<code class="rounded-4 bg-surface-gray-2 px-1 text-xs">
				studio: { type: "select", options: ["sm", "md"] }
			</code>
			to it.
		</p>
	</div>
</template>
