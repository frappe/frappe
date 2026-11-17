<script lang="ts">
import { Comment, Fragment, defineComponent, onBeforeUnmount, type VNode } from "vue"
import { useRoute } from "vue-router"
import {
	activeVariantIndex,
	registerVariantSet,
	releaseVariantSet,
	retainVariantSet,
	variantOptionNames,
} from "@/utils/variants"

/**
 * One container that holds several named alternatives and renders one of them. The children
 * are the options, in order, and each one is named by its own block (`variantOptionName`). The
 * choice is kept in the URL (?v=<set>.<option>), so any combination is a link.
 */
export default defineComponent({
	name: "Variants",
	// the options keep their own data-component-id. This block exists only in the registry.
	inheritAttrs: false,
	props: {
		name: { type: String, default: "Variant" },
	},
	setup(props, { slots, attrs }) {
		const route = useRoute()
		const blockId = String(attrs["data-component-id"] || "")
		retainVariantSet(blockId)
		onBeforeUnmount(() => releaseVariantSet(blockId))

		return () => {
			// child blocks arrive in a fragment, and the options are its children. Vue warns when a
			// slot is read outside the render function, so the set is resolved here.
			const options = flattenSlot(slots.default?.() || [])
			if (!options.length) return null
			const optionBlocks = options.map(optionBlock)
			const set = registerVariantSet({
				blockId,
				name: props.name,
				options: variantOptionNames({ children: optionBlocks }),
				optionIds: optionBlocks.map((block) => block?.componentId),
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
