import useStudioStore from "@/stores/studioStore"
import Block from "@/utils/block"
import { getComponentBlock, throttle } from "@/utils/helpers"
import { useDropZone } from "@vueuse/core"
import { Ref } from "vue"

const store = useStudioStore()

export function useCanvasDropZone(
	canvasContainer: Ref<HTMLElement>,
	block: Ref<Block>,
	findBlock: (id: string) => Block | null,
) {
	const { isOverDropZone } = useDropZone(canvasContainer, {
		onDrop: (_files, ev) => {
			const droppedComponentName = store.dnd.source
			const { parentComponent, index, slotName } = store.dnd.target

			if (droppedComponentName && parentComponent) {
				const newBlock = getComponentBlock(droppedComponentName)
				if (slotName) {
					parentComponent.updateSlot(slotName, newBlock)
				} else {
					parentComponent.addChild(newBlock, index)
				}
			}
		},
		onOver: (_files, ev) => {
			const { parentComponent, index } = getDropTarget(ev)
			if (parentComponent) {
				store.hoveredBlock = parentComponent.componentId
				updateDropTarget(parentComponent, index)
			}
		},
	})

	const getDropTarget = (ev: DragEvent) => {
		const element = document.elementFromPoint(ev.clientX, ev.clientY) as HTMLElement
		const targetElement = element.closest(".__studio_component__") as HTMLElement

		let parentComponent = block.value
		let slotName
		let index = parentComponent.children.length

		if (targetElement && targetElement.dataset.componentId) {
			parentComponent = findBlock(targetElement.dataset.componentId) || parentComponent
			// Walk up the tree until we find a component that can have children
			while (parentComponent && !parentComponent.canHaveChildren()) {
				parentComponent = parentComponent.getParentBlock()
			}
			slotName = targetElement.dataset.slotName || store.selectedSlot?.slotName
			index = findDropIndex(ev, parentComponent)
		}
		return { parentComponent, slotName, index }
	}

	const findDropIndex = (ev: DragEvent, parentComponent: Block): number => {
		const parentEl = document.querySelector(
			`[data-component-id="${parentComponent.componentId}"]`,
		) as HTMLElement
		if (!parentEl) return parentComponent.children.length

		const childElements = Array.from(
			parentEl.querySelectorAll(":scope > .__studio_component__"),
		) as HTMLElement[]
		if (childElements.length === 0) return 0

		const direction = getLayoutDirection(parentEl)
		const mousePos = direction === "row" ? ev.clientX : ev.clientY

		// Get all child positions
		const childPositions = childElements.map((child, idx) => {
			const rect = child.getBoundingClientRect()
			const midPoint = direction === "row" ? rect.left + rect.width / 2 : rect.top + rect.height / 2
			return { midPoint, idx }
		})

		// Find the closest child to the mouse position
		let closestIndex = 0
		let minDistance = Infinity

		childPositions.forEach(({ midPoint, idx }) => {
			const distance = Math.abs(midPoint - mousePos)
			if (distance < minDistance) {
				minDistance = distance
				closestIndex = idx
			}
		})

		// Determine if we should insert before or after the closest child
		// if mouse is closer to left/top side of the child, insert before, else after
		return mousePos <= childPositions[closestIndex].midPoint ? closestIndex : closestIndex + 1
	}

	const getLayoutDirection = (element: HTMLElement): "row" | "column" => {
		const style = window.getComputedStyle(element)
		const display = style.display
		if (display === "flex" || display === "inline-flex") {
			return style.flexDirection.includes("row") ? "row" : "column"
		} else if (display === "grid" || display == "inline-grid") {
			return style.gridAutoFlow.includes("row") ? "row" : "column"
		}
		return "column"
	}

	const updateDropTarget = throttle((parentComponent: Block | null, index) => {
		// append placeholder component to the dom directly
		// to avoid re-rendering the whole canvas
		if (!parentComponent || !store.dnd.target?.element) return
		const newParent = document.querySelector(`.__studio_component__[data-component-id="${parentComponent.componentId}"]`)
		if (!newParent) return

		// Append the element to the new parent
		newParent.insertBefore(store.dnd.target.element, newParent.children[index])
		store.dnd.target.parentComponent = parentComponent
		store.dnd.target.index = index
	}, 130)

	return { isOverDropZone }
}
