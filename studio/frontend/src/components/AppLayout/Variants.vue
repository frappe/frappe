<script lang="ts">
import { Comment, Fragment, defineComponent, onBeforeUnmount, type VNode } from "vue"
import { useRoute } from "vue-router"
import {
	activeVariantIndex,
	registerVariantSet,
	releaseVariantSet,
	retainVariantSet,
} from "@/utils/variants"

/**
 * One container holding N named alternative subtrees and rendering one. Children are the
 * options, in order, each named by its own block (`variantOptionName`); the choice is mirrored
 * to the URL (?v=<set>.<option>) so any combination is a shareable link.
 */
export default defineComponent({
	name: "Variants",
	// the options keep their own data-component-id; this block exists only in the registry
	inheritAttrs: false,
	props: {
		name: { type: String, default: "Variant" },
	},
	setup(props, { slots, attrs }) {
		const route = useRoute()
		// the rendered block's id, so "Keep" can resolve this set back to its editor node
		const blockId = String(attrs["data-component-id"] || "")
		retainVariantSet(blockId)
		onBeforeUnmount(() => releaseVariantSet(blockId))

		return () => {
			// child blocks arrive wrapped in a fragment; the options are its children. Read here
			// and not in setup: a slot read outside the render function warns, and freezes the
			// options as they were when the block mounted.
			const options = flattenSlot(slots.default?.() || [])
			if (!options.length) return null
			const set = registerVariantSet({
				blockId,
				name: props.name,
				options: options.map((option, index) => optionBlock(option)?.variantOptionName || `Option ${index + 1}`),
				// the option blocks' ids, so the pill can outline the rendered option on hover
				optionIds: options.map((option) => optionBlock(option)?.componentId),
			})
			return options[Math.min(activeVariantIndex(set, String(route?.query?.v ?? "")), options.length - 1)]
		}
	},
})

function optionBlock(vnode: VNode) {
	return (vnode.props as any)?.block as { componentId?: string; variantOptionName?: string } | undefined
}

function flattenSlot(vnodes: VNode[]): VNode[] {
	const flattened: VNode[] = []
	for (const vnode of vnodes) {
		if (vnode.type === Comment) continue
		if (vnode.type === Fragment && Array.isArray(vnode.children)) {
			flattened.push(...flattenSlot(vnode.children as VNode[]))
		} else {
			flattened.push(vnode)
		}
	}
	return flattened
}
</script>
