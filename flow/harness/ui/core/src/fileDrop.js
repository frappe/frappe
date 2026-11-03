import { onBeforeUnmount, provide, ref, watch } from "vue"

// A drag from the desktop carries files; text or a link dragged within the page does not.
export function dragHasFiles(event) {
	return Array.from(event.dataTransfer?.types ?? []).includes("Files")
}

// dragenter and dragleave fire for each child the pointer crosses, so the drag is over the
// target until every enter has had its leave.
export function dragDepth() {
	let depth = 0
	return {
		enter: () => ++depth > 0,
		leave: () => (depth = Math.max(0, depth - 1)) > 0,
		reset: () => (depth = 0),
	}
}

// Files dropped anywhere on a chat go to its composer, as if picked with Attach; the
// composer shows the drop target while they are over the chat. A drop the composer cannot
// take now is still caught, so a near miss does not open the file in the tab.
export function provideFileDrop(target, composer) {
	const dragging = ref(false)
	provide("fileDragging", dragging)
	const depth = dragDepth()
	const accepts = () => Boolean(composer.value?.canAttach())
	const handlers = {
		dragenter(event) {
			if (!dragHasFiles(event)) return
			event.preventDefault()
			dragging.value = depth.enter() && accepts()
		},
		dragover(event) {
			if (!dragHasFiles(event)) return
			event.preventDefault()
			event.dataTransfer.dropEffect = accepts() ? "copy" : "none"
		},
		dragleave(event) {
			if (dragHasFiles(event)) dragging.value = depth.leave() && dragging.value
		},
		drop(event) {
			if (!dragHasFiles(event)) return
			event.preventDefault()
			depth.reset()
			dragging.value = false
			if (accepts()) composer.value.addFiles(Array.from(event.dataTransfer.files))
		},
	}
	const bind = (el, method) => {
		for (const [name, handler] of Object.entries(handlers)) el?.[method](name, handler)
	}
	watch(
		() => target.value,
		(el, old) => {
			bind(old, "removeEventListener")
			bind(el, "addEventListener")
		},
		{ immediate: true },
	)
	onBeforeUnmount(() => bind(target.value, "removeEventListener"))
	return dragging
}
