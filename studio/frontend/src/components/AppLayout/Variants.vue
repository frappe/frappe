<script lang="ts">
import { Comment, Fragment, defineComponent, onBeforeUnmount, type PropType, type VNode } from "vue"
import { parseVariantOptions, releaseVariantSet, useVariantSet } from "@/utils/variants"

/**
 * One container holding N named alternative subtrees and rendering one. Children are the
 * options, in order; `options` names them for the switcher pill, and the choice is mirrored
 * to the URL (?v=<set>.<option>) so any combination is a shareable link.
 */
export default defineComponent({
	name: "Variants",
	// the options keep their own data-component-id; this block exists only in the registry
	inheritAttrs: false,
	props: {
		name: { type: String, default: "Variant" },
		options: { type: [Array, String] as PropType<string[] | string>, default: () => [] },
	},
	setup(props, { slots, attrs }) {
		const options = parseVariantOptions(props.options)
		// the rendered block's id, so "Keep" can resolve this set back to its editor node
		const blockId = String(attrs["data-component-id"] || "")
		// the option blocks' ids, so the pill can outline the rendered option on hover
		const optionIds = flattenSlot(slots.default?.() || []).map(
			(vnode) => (vnode.props as any)?.block?.componentId as string | undefined,
		)
		const { key, activeIndex } = useVariantSet({ name: props.name, options, blockId, optionIds })
		onBeforeUnmount(() => releaseVariantSet(key))

		return () => {
			// child blocks arrive wrapped in a fragment; the options are its children
			const children = flattenSlot(slots.default?.() || [])
			if (!children.length) return null
			return children[Math.min(activeIndex.value, children.length - 1)]
		}
	},
})

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
