import components from "@/data/components"
import useStudioStore from "@/stores/studioStore"
import Block from "@/utils/block"
import { getComponentBlock, throttle } from "@/utils/helpers"
import { useDropZone } from "@vueuse/core"
import { Ref } from "vue"

const store = useStudioStore()
type LayoutDirection = "row" | "column"

export function useCanvasDropZone(
	canvasContainer: Ref<HTMLElement>,
	block: Ref<Block | null>,
	findBlock: (id: string) => Block | null,
) {
	const { isOverDropZone } = useDropZone(canvasContainer, {
		onDrop: (_files, ev) => {
			const droppedComponentName = ev.dataTransfer?.getData("componentName")
			const { parentComponent, index, slotName } = store.dropTarget

			if (droppedComponentName && parentComponent) {
				const componentConfig = components.get(droppedComponentName)
				let newBlock: Block

				if (componentConfig.proxyComponent) {
					newBlock = getComponentBlock(componentConfig.proxyComponent)
				} else {
					newBlock = getComponentBlock(droppedComponentName)
				}

				if (componentConfig?.editInFragmentMode) {
					store.editOnCanvas(newBlock, () => {})
				} else {
					if (slotName) {
						parentComponent.updateSlot(slotName, newBlock)
					} else {
						parentComponent.addChild(newBlock, index)
					}
				}
			}
		},
		onOver: (_files, ev) => {
			const { parentComponent, index, layoutDirection } = findDropTarget(ev)
			if (parentComponent) {
				store.hoveredBlock = parentComponent.componentId
				updateDropTarget(ev, parentComponent, index, layoutDirection)
			}
		},
	})

	const getBlockElement = (block: Block) => {
		const breakpoint = store.hoveredBreakpoint || store.activeBreakpoint;
		return document.querySelector(`.__studio_component__[data-component-id="${block.componentId}"][data-breakpoint="${breakpoint}"]`) as HTMLElement;
	}

	const findDropTarget = (ev: DragEvent) => {
		if (store.dropTarget.x === ev.x && store.dropTarget.y === ev.y) return {}

		const element = document.elementFromPoint(ev.clientX, ev.clientY) as HTMLElement
		const targetElement = element.closest(".__studio_component__") as HTMLElement

		// set the hoveredBreakpoint from the target element to show placeholder at the correct breakpoint canvas
		const breakpoint = targetElement?.dataset.breakpoint || store.activeBreakpoint;
		if (breakpoint !== store.hoveredBreakpoint) {
			store.hoveredBreakpoint = breakpoint;
		}

		let parentComponent = block.value
		let slotName
		let layoutDirection = "column" as LayoutDirection
		let index = parentComponent?.children.length || 0

		if (targetElement && targetElement.dataset.componentId) {
			parentComponent = findBlock(targetElement.dataset.componentId) || parentComponent
			// Walk up the tree until we find a component that can have children
			while (parentComponent && !parentComponent.canHaveChildren()) {
				parentComponent = parentComponent.getParentBlock()
			}

			if (parentComponent) {
				const parentElement = getBlockElement(parentComponent)
				layoutDirection = getLayoutDirection(parentElement)
				index = findDropIndex(ev, parentElement, layoutDirection)
				slotName = targetElement.dataset.slotName || store.selectedSlot?.slotName
			}
		}
		return { parentComponent, slotName, index, layoutDirection }
	}

	const findDropIndex = (ev: DragEvent, parentElement: HTMLElement, layoutDirection: LayoutDirection): number => {
		const childElements = Array.from(
			parentElement.querySelectorAll(":scope > .__studio_component__, #placeholder"),
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

	const updateDropTarget = throttle((ev: DragEvent, parentComponent: Block | null, index: number, layoutDirection: LayoutDirection) => {
		// append placeholder component to the dom directly
		// to avoid re-rendering the whole canvas
		const { placeholder } = store.dropTarget
		if (!parentComponent || !placeholder) return
		const newParent = getBlockElement(parentComponent)
		if (!newParent) return

		if (store.dropTarget.parentComponent?.componentId === parentComponent.componentId && store.dropTarget.index === index) return

		// flip placeholder border as per layout direction to avoid shifting elements too much
		if (layoutDirection === "row") {
			placeholder.classList.remove("horizontal-placeholder")
			placeholder.classList.add("vertical-placeholder")
		} else {
			placeholder.classList.remove("vertical-placeholder")
			placeholder.classList.add("horizontal-placeholder")
		}

		// add the placeholder to the new parent
		// exclude placeholder as its going to move with this update
		const children = Array.from(newParent.children).filter((child) => child.id !== "placeholder")
		if (index >= children.length) {
			newParent.appendChild(placeholder)
		} else {
			newParent.insertBefore(placeholder, children[index])
		}

		store.dropTarget.parentComponent = parentComponent
		store.dropTarget.index = index
		store.dropTarget.x = ev.x
		store.dropTarget.y = ev.y
	}, 130)

	return { isOverDropZone }
}
