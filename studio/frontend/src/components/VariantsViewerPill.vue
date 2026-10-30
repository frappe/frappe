<template>
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
			<VariantRows :rows="rows" :can-keep="canKeep" @pick="pickRow" @keep="keepRow" @hover="hoverRow" />
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
				</span>
			</Button>
			<VariantRows v-else :rows="rows" :can-keep="canKeep" solo @pick="pickRow" @keep="keepRow" @hover="hoverRow" />
		</div>
	</div>

	<BlockOutline :rect="outlineRect" />
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { onClickOutside, useEventListener } from "@vueuse/core"
import { Button, call, dialog, toast } from "frappe-ui"
import BlockOutline from "@/components/BlockOutline.vue"
import VariantRows from "@/components/VariantRows.vue"
import { useBlockOutline } from "@/utils/useBlockOutline"
import {
	activeVariantIndex,
	keepDialogText,
	useMountedVariantSets,
	withChoice,
	type VariantRow,
	type VariantSet,
} from "@/utils/variants"

// The variants pill on the live app, bottom right. One rendered set shows inline; more collapse
// behind a count and expand into a panel. Every choice is mirrored to the URL, so the
// current combination is a link.
const route = useRoute()
const router = useRouter()
const sets = useMountedVariantSets()

// Keep needs a developer bench and write access, so a hosted site without developer mode
// shows the switcher without it; answered server side, so a page view costs no round trip
const canKeep = Boolean((window as any).can_edit_app)

// Rows in page order (top to bottom, then left to right), worked out when the panel
// opens and when the page's sets change, not continuously.
const order = ref<string[]>([])
const orderedSets = computed(() => {
	const o = order.value
	return [...sets.value].sort((a, b) => (o.indexOf(a.blockId) + 1 || 99) - (o.indexOf(b.blockId) + 1 || 99))
})
const rows = computed<VariantRow[]>(() =>
	orderedSets.value.map((s) => ({
		key: s.blockId,
		name: s.name,
		options: s.options,
		activeIndex: activeIndex(s),
	})),
)
const setOf = (row: VariantRow) => sets.value.find((s) => s.blockId === row.key)
function pickRow(row: VariantRow, option: string) {
	const set = setOf(row)
	if (set) pick(set, option)
}
function keepRow(row: VariantRow) {
	const set = setOf(row)
	if (set) keepVariant(set)
}
function hoverRow(row: VariantRow | null) {
	hover(row ? (setOf(row) ?? null) : null)
}
function sortRows() {
	const at = (set: VariantSet) => elementOf(set)?.getBoundingClientRect() ?? { top: 1e9, left: 0 }
	order.value = [...sets.value]
		.sort((a, b) => at(a).top - at(b).top || at(a).left - at(b).left)
		.map((s) => s.blockId)
}
watch(() => sets.value.length, () => nextTick(sortRows), { flush: "post" })

const multi = computed(() => rows.value.length > 1)

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

function pick(set: VariantSet, value: string) {
	const index = set.options.indexOf(value)
	if (index < 0) return
	const serialized = withChoice(String(route.query.v ?? ""), set.token, set.options, index)
	router.replace({ query: { ...route.query, v: serialized || undefined } })
}

function activeIndex(set: VariantSet) {
	return activeVariantIndex(set, String(route.query.v ?? ""))
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
			// the preview re-reads the page over the socket, but a published one is cached until
			// the next publish, so only a reload can show the block going away
			if (!window.is_preview) window.location.reload()
		},
	})
}

const { rect: outlineRect, outline, measure } = useBlockOutline(true)
const hovered = ref<VariantSet | null>(null)

function elementOf(set: VariantSet) {
	// the Variants block renders no element of its own, so find its rendered option
	const optionId = set.optionIds[activeIndex(set)]
	return optionId ? document.querySelector(`[data-component-id="${optionId}"]`) : null
}
function hover(set: VariantSet | null) {
	hovered.value = set
	outline(set ? () => elementOf(set) : null)
}
// A row can go away under the pointer without a mouseleave: the panel closes, the route changes.
watch([() => route.path, open], () => hover(null))
// A switch replaces the outlined element and reflows the page; re-measure once the swap has landed.
watch(() => route.query.v, () => hovered.value && nextTick(measure))
</script>
