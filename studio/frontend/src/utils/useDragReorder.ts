import { ref } from "vue"

/**
 * Reorder a list of rows by dragging a grip handle. A row is draggable only while its own
 * grip is pressed (`dragHandleIndex`), so text selection inside the row's inputs keeps
 * working. `move` applies the reorder; how the list is stored is the caller's business.
 */
export function useDragReorder(move: (from: number, to: number) => void) {
	const dragIndex = ref<number | null>(null)
	const dragHandleIndex = ref<number | null>(null)

	function onDragStart(index: number, event: DragEvent) {
		dragIndex.value = index
		event.dataTransfer?.setData("text/plain", String(index))
		if (event.dataTransfer) event.dataTransfer.effectAllowed = "move"
	}

	function onDrop(index: number) {
		const from = dragIndex.value
		resetDrag()
		if (from !== null && from !== index) move(from, index)
	}

	function resetDrag() {
		dragIndex.value = null
		dragHandleIndex.value = null
	}

	return { dragIndex, dragHandleIndex, onDragStart, onDrop, resetDrag }
}
