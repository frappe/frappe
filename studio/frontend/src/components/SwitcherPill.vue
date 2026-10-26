<template>
	<DefineRow v-slot="{ s, solo }">
		<!-- In the panel each row is a subgrid, so names, options and Keep line up across rows. -->
		<div
			class="items-center"
			:class="solo ? 'flex gap-2' : 'col-span-full grid grid-cols-subgrid'"
			@mouseenter="hover(s)"
			@mouseleave="hover(null)"
		>
			<span class="flex min-w-0 items-center gap-2 text-p-sm" :class="solo ? 'text-ink-gray-5' : 'text-ink-gray-8'">
				<span v-if="isOffDefault(s)" class="size-1.5 shrink-0 rounded-full bg-surface-blue-7" aria-hidden="true" />
				{{ s.name }}
			</span>
			<TabButtons
				class="justify-self-start"
				:options="opts(s)"
				:model-value="s.options[activeIndex(s)]"
				@update:model-value="(v: TabButtonValue) => pick(s, v)"
			/>
			<template v-if="canKeep">
				<span class="flex shrink-0 justify-end">
					<Button
						:class="solo || isOffDefault(s) || hovered?.key === s.key ? '' : 'invisible'"
						variant="ghost"
						:aria-label="`Keep ${s.options[activeIndex(s)]} for ${s.name}`"
						@click="keepVariant(s)"
					>
						Keep
					</Button>
				</span>
			</template>
		</div>
	</DefineRow>

	<div
		v-if="rows.length"
		ref="stack"
		class="pointer-events-none fixed inset-x-3 bottom-3 z-50 flex flex-col items-end gap-2"
	>
		<div
			v-if="multi && open"
			id="studio-variants-panel"
			class="pointer-events-auto max-h-[60vh] w-max max-w-full overflow-y-auto rounded-5 bg-surface-elevation-2 p-3 shadow-lg ring-1 ring-outline-gray-1"
		>
			<div
				class="grid items-center gap-x-4 gap-y-3"
				:class="canKeep ? 'grid-cols-[auto_auto_auto]' : 'grid-cols-[auto_auto]'"
			>
				<Row v-for="s in rows" :key="s.key" :s="s" />
			</div>
		</div>
		<div
			data-pill="variants"
			class="pointer-events-auto rounded-5 bg-surface-elevation-2 shadow-lg ring-1 ring-outline-gray-1"
			:class="multi ? 'p-1' : 'px-3 py-2'"
		>
			<Button
				v-if="multi"
				variant="ghost"
				icon-left="lucide-layers"
				aria-label="Variants"
				aria-controls="studio-variants-panel"
				:aria-expanded="open"
				@click="toggle"
			>
				<span class="flex items-center gap-1.5">
					<span class="text-p-sm text-ink-gray-8">Variants</span>
					<span class="text-p-sm tabular-nums text-ink-gray-5">{{ rows.length }}</span>
					<span v-if="anyOffDefault" class="size-1.5 rounded-full bg-surface-blue-7" aria-hidden="true" />
				</span>
			</Button>
			<Row v-else :s="rows[0]" solo />
		</div>
	</div>

	<!-- The hovered set's rendered option, in the editor's block-selection ring
	     (ComponentEditor: ring-2 ring-inset ring-outline-blue-4) -->
	<div
		v-if="box && hovered"
		class="pointer-events-none fixed z-50 ring-2 ring-inset ring-outline-blue-4"
		:style="{ left: `${box.left}px`, top: `${box.top}px`, width: `${box.width}px`, height: `${box.height}px` }"
		aria-hidden="true"
	/>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, shallowRef, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { createReusableTemplate, onClickOutside, useEventListener } from "@vueuse/core"
import { Button, TabButtons, call, dialog, toast, type TabButtonValue } from "frappe-ui"
import { choiceIndex, keepDialogText, useMountedVariantSets, withChoice, type VariantSet } from "@/utils/variants"

// The viewer's variants pill, bottom right. One mounted set renders inline; more collapse
// behind a count and expand into a panel. Every choice is mirrored to the URL, so the
// current combination is a link.
const [DefineRow, Row] = createReusableTemplate<{ s: VariantSet; solo?: boolean }>({
	inheritAttrs: false,
	// Declared, so a bare `solo` arrives as true rather than as an empty attribute.
	props: { s: { type: Object, required: true }, solo: Boolean },
})

const route = useRoute()
const router = useRouter()
const sets = useMountedVariantSets()

const canKeep = ref(false)
onMounted(async () => {
	if ((window as any).is_guest) return
	try {
		canKeep.value = Boolean(await call("frappe.studio.api.check_app_permission"))
	} catch {
		canKeep.value = false
	}
})

// Rows in page order (top to bottom, then left to right), worked out when the panel
// opens and when the page's sets change, not continuously.
const order = ref<string[]>([])
const rows = computed(() => {
	const o = order.value
	return [...sets.value].sort((a, b) => (o.indexOf(a.key) + 1 || 99) - (o.indexOf(b.key) + 1 || 99))
})
function sortRows() {
	const at = (set: VariantSet) => elementOf(set)?.getBoundingClientRect() ?? { top: 1e9, left: 0 }
	order.value = [...sets.value].sort((a, b) => at(a).top - at(b).top || at(a).left - at(b).left).map((s) => s.key)
}
watch(() => sets.value.length, () => nextTick(sortRows), { flush: "post" })

const multi = computed(() => rows.value.length > 1)
const anyOffDefault = computed(() => rows.value.some(isOffDefault))

const open = ref(false)
function toggle() {
	open.value = !open.value
	if (open.value) sortRows()
}
watch(multi, (m) => !m && (open.value = false))

const stack = ref<HTMLElement | null>(null)
onClickOutside(stack, () => (open.value = false))
useEventListener(document, "keydown", (e: KeyboardEvent) => {
	if (e.key !== "Escape" || !open.value) return
	open.value = false
	;(document.querySelector('[data-pill="variants"]') as HTMLElement | null)?.querySelector("button")?.focus()
})

const opts = (set: VariantSet) => set.options.map((option) => ({ value: option, label: option }))
function pick(set: VariantSet, value: TabButtonValue) {
	const index = set.options.indexOf(String(value))
	if (index < 0) return
	const serialized = withChoice(String(route.query.v ?? ""), set.key, set.options, index)
	router.replace({ query: { ...route.query, v: serialized || undefined } })
}

function activeIndex(set: VariantSet) {
	return choiceIndex(String(route.query.v ?? ""), set.key, set.options)
}

function isOffDefault(set: VariantSet) {
	return activeIndex(set) > 0
}

function keepVariant(set: VariantSet) {
	const option = activeIndex(set)
	dialog.confirm({
		...keepDialogText(set.options, option),
		confirmLabel: "Keep",
		onConfirm: async () => {
			try {
				await call("frappe.studio.doctype.studio_page.studio_page.keep_variant", {
					app_name: (window as any).app_name,
					page_name: route.meta.pageName,
					block_id: set.blockId,
					option_index: option,
				})
			} catch (error: any) {
				throw new Error(error?.messages?.join(", ") || "Could not keep the variant")
			}
			toast.success(`Kept ${set.options[option]}`)
			window.location.reload()
		},
	})
}

// -- hover outline over the hovered set's rendered option --
const hovered = ref<VariantSet | null>(null)
const box = shallowRef<DOMRect | null>(null)

function elementOf(set: VariantSet) {
	// the Variants block renders no element of its own, so find its rendered option
	const blockId = set.optionIds?.[activeIndex(set)] || set.blockId
	return blockId ? document.querySelector(`[data-component-id="${blockId}"]`) : null
}
function hover(set: VariantSet | null) {
	hovered.value = set
	box.value = set ? (elementOf(set)?.getBoundingClientRect() ?? null) : null
}
// A row can go away under the pointer without a mouseleave: the panel closes, the route changes.
watch([() => route.path, open], () => hover(null))
// A switch replaces the outlined element and reflows the page; re-measure once the swap has landed.
watch(
	() => route.query.v,
	() => nextTick(() => hovered.value && hover(hovered.value)),
)
useEventListener(window, "resize", () => hovered.value && hover(hovered.value))
useEventListener(window, "scroll", () => hovered.value && hover(hovered.value), { capture: true, passive: true })
</script>
