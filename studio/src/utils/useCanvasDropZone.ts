import useCanvasStore from "@/stores/canvasStore"
import Block from "@/utils/block"
import { getComponentBlock } from "@/utils/helpers"
import { useDropZone } from "@vueuse/core"
import { Ref } from "vue"

const canvasStore = useCanvasStore()
type LayoutDirection = "row" | "column"

export function useCanvasDropZone(
	canvasContainer: Ref<HTMLElement>,
	block: Ref<Block | null>,
	findBlock: (id: string) => Block | null,
) {
	const { isOverDropZone } = useDropZone(canvasContainer, {
		onDrop: (_files, ev) => {
			const droppedComponentName = ev.dataTransfer?.getData("componentName")
			const { parentComponent, index, slotName } = canvasStore.dropTarget

			if (droppedComponentName && parentComponent) {
				function saveBlock(block: Block) {
					if (slotName) {
						parentComponent?.updateSlot(slotName, block)
					} else {
						parentComponent?.addChild(block, index)
					}
				}

				let newBlock = getComponentBlock(droppedComponentName)
				if (newBlock.editInFragmentMode()) {
					canvasStore.editOnCanvas(
						newBlock,
						(editedBlock: Block) => saveBlock(editedBlock),
						`Save ${droppedComponentName}`
					)
				} else {
					saveBlock(newBlock)
				}
			}
		},
		onOver: (_files, ev) => {
			const { parentComponent, slotName, index, layoutDirection } = findDropTarget(ev)
			if (parentComponent) {
				canvasStore.activeCanvas?.setHoveredBlock(parentComponent.componentId)
				updateDropTarget(ev, parentComponent, slotName, index, layoutDirection)
			}
		},
	})

	const getBlockElement = (block: Block) => {
		const breakpoint = canvasStore.activeCanvas?.hoveredBreakpoint || canvasStore.activeCanvas?.activeBreakpoint
		return document.querySelector(`.__studio_component__[data-component-id="${block.componentId}"][data-breakpoint="${breakpoint}"]`) as HTMLElement;
	}

	const findDropTarget = (ev: DragEvent) => {
		if (canvasStore.dropTarget.x === ev.x && canvasStore.dropTarget.y === ev.y) return {}

		const element = document.elementFromPoint(ev.clientX, ev.clientY) as HTMLElement
		const targetElement = element.closest(".__studio_component__") as HTMLElement

		// set the hoveredBreakpoint from the target element to show placeholder at the correct breakpoint canvas
		const breakpoint = targetElement?.dataset.breakpoint || canvasStore.activeCanvas?.activeBreakpoint || null
		if (breakpoint !== canvasStore.activeCanvas?.hoveredBreakpoint) {
			canvasStore.activeCanvas?.setHoveredBreakpoint(breakpoint)
		}

		let parentComponent = block.value
		let slotName = null
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
				if (canvasStore.activeCanvas?.selectedSlot?.parentBlockId === parentComponent.componentId) {
					slotName = canvasStore.activeCanvas.selectedSlot?.slotName
				}
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

	const updateDropTarget = (
		ev: DragEvent,
		parentComponent: Block | null,
		slotName: string | null,
		index: number,
		layoutDirection: LayoutDirection
	) => {
		// append placeholder component to the dom directly
		// to avoid re-rendering the whole canvas
		const { placeholder } = canvasStore.dropTarget
		if (!parentComponent || !placeholder) return
		let newParent = getBlockElement(parentComponent)
		if (!newParent) return

		if (slotName) {
			const slotElement = newParent.querySelector(`[data-slot-name="${slotName}"].__studio_component_slot__`) as HTMLElement
			if (slotElement) {
				newParent = slotElement
			}
		}

		if (canvasStore.dropTarget.parentComponent?.componentId === parentComponent.componentId && canvasStore.dropTarget.index === index) return

		// flip placeholder border as per layout direction to avoid shifting elements too much
		placeholder.classList.toggle("vertical-placeholder", layoutDirection === "row")
		placeholder.classList.toggle("horizontal-placeholder", layoutDirection === "column")

		// add the placeholder to the new parent
		// exclude placeholder as its going to move with this update
		const children = Array.from(newParent.children).filter((child) => child.id !== "placeholder")
		if (index >= children.length) {
			newParent.appendChild(placeholder)
		} else {
			newParent.insertBefore(placeholder, children[index])
		}

		canvasStore.dropTarget.parentComponent = parentComponent
		canvasStore.dropTarget.index = index
		canvasStore.dropTarget.slotName = slotName
		canvasStore.dropTarget.x = ev.x
		canvasStore.dropTarget.y = ev.y
	}

	return { isOverDropZone }
}
