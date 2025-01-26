import useStudioStore from "@/stores/studioStore"
import Block from "@/utils/block"
import { getComponentBlock, throttle } from "@/utils/helpers"
import { useDropZone } from "@vueuse/core"
import { Ref } from "vue"

const store = useStudioStore()
type LayoutDirection = "row" | "column"

export function useCanvasDropZone(
	canvasContainer: Ref<HTMLElement>,
	block: Ref<Block>,
	findBlock: (id: string) => Block | null,
) {
	const { isOverDropZone } = useDropZone(canvasContainer, {
		onDrop: (_files, ev) => {
			const droppedComponentName = store.dragState.source
			const { parentComponent, index, slotName } = store.dragState.target

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
			const { parentComponent, index, layoutDirection } = getDropTarget(ev)
			if (parentComponent) {
				store.hoveredBlock = parentComponent.componentId
				updateDropTarget(parentComponent, index, layoutDirection)
			}
		},
	})

	const getDropTarget = (ev: DragEvent) => {
		const element = document.elementFromPoint(ev.clientX, ev.clientY) as HTMLElement
		const targetElement = element.closest(".__studio_component__") as HTMLElement

		let parentComponent = block.value
		let slotName
		let layoutDirection = "column" as LayoutDirection
		let index = parentComponent.children.length

		if (targetElement && targetElement.dataset.componentId) {
			parentComponent = findBlock(targetElement.dataset.componentId) || parentComponent
			// Walk up the tree until we find a component that can have children
			while (parentComponent && !parentComponent.canHaveChildren()) {
				parentComponent = parentComponent.getParentBlock()
			}

			if (parentComponent) {
				const parentElement = document.querySelector(
					`[data-component-id="${parentComponent.componentId}"]:not(.editor)`,
				) as HTMLElement
				layoutDirection = getLayoutDirection(parentElement)
				index = findDropIndex(ev, parentElement, layoutDirection)
				slotName = targetElement.dataset.slotName || store.selectedSlot?.slotName
			}
		}
		return { parentComponent, slotName, index, layoutDirection }
	}

	const findDropIndex = (ev: DragEvent, parentElement: HTMLElement, layoutDirection: LayoutDirection): number => {
		const childElements = Array.from(
			parentElement.querySelectorAll(":scope > .__studio_component__"),
		) as HTMLElement[]
		if (childElements.length === 0) return 0

		const mousePos = layoutDirection === "row" ? ev.clientX : ev.clientY

		// Get all child positions
		const childPositions = childElements.map((child, idx) => {
			const rect = child.getBoundingClientRect()
			const midPoint = layoutDirection === "row" ? rect.left + rect.width / 2 : rect.top + rect.height / 2
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

	const getLayoutDirection = (element: HTMLElement): LayoutDirection => {
		const style = window.getComputedStyle(element)
		const display = style.display
		if (display === "flex" || display === "inline-flex") {
			return style.flexDirection.includes("row") ? "row" : "column"
		} else if (display === "grid" || display == "inline-grid") {
			return style.gridAutoFlow.includes("row") ? "row" : "column"
		}
		return "column"
	}

	const updateDropTarget = throttle((parentComponent: Block | null, index: number, layoutDirection: LayoutDirection) => {
		// append placeholder component to the dom directly
		// to avoid re-rendering the whole canvas
		const { placeholder } = store.dragState.target
		if (!parentComponent || !placeholder) return
		const newParent = document.querySelector(`.__studio_component__[data-component-id="${parentComponent.componentId}"]`)
		if (!newParent) return

		if (store.dragState.target.parentComponent === parentComponent && store.dragState.target.index === index) return

		// flip placeholder border as per layout direction to avoid shifting elements too much
		if (layoutDirection === "row") {
			placeholder.classList.remove("horizontal-placeholder")
			placeholder.classList.add("vertical-placeholder")
		} else {
			placeholder.classList.remove("vertical-placeholder")
			placeholder.classList.add("horizontal-placeholder")
		}

		// Append the placeholder to the new parent
		newParent.insertBefore(placeholder, newParent.children[index])
		store.dragState.target.parentComponent = parentComponent
		store.dragState.target.index = index
	}, 130)

	return { isOverDropZone }
}
