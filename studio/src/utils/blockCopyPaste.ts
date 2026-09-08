import { dialog, toast, call } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import useCodeStore from "@/stores/codeStore"
import { studioPages } from "@/data/studioPages"
import { hasPageScript as hasCompiledPageScript } from "@/data/studioPageScripts"
import { getBlockCopy, getBlockCopyWithoutParent, getBlockInstance, isJSONString } from "@/utils/serializer"
import { setClipboardData } from "@/utils/helpers"
import Block from "@/utils/block"
import type { BlockOptions } from "@/types"

const CLIPBOARD_FORMAT = "studio-copied-blocks"
const CLIPBOARD_PREFIX = `${CLIPBOARD_FORMAT}:`

export interface PageCopy {
	page_title?: string
	allow_guest?: 0 | 1
	resources: Record<string, any>[]
	variables: Record<string, any>[]
	script: string
}

interface Dependencies {
	components: Record<string, any>[]
	files: { path: string; content: string }[]
	resources: Record<string, any>[]
	variables: Record<string, any>[]
}

interface ClipboardSource {
	origin: string
	app: string
	page: string
	hasPageScript: boolean
}

interface ClipboardPayload extends Partial<Dependencies> {
	blocks: BlockOptions[]
	page?: PageCopy
	source?: ClipboardSource
}

export function copyEntirePage() {
	const page = useStudioStore().activePage
	const root = useCanvasStore().activeCanvas?.getRootBlock()
	if (!page || !root) return
	const blocks = [getBlockCopyWithoutParent(root)]
	const payload = studioPages.runDocMethod
		.submit({ name: page.name, method: "get_copy", blocks })
		.then((response: any) => {
			const { components, files, ...pageCopy } = response.message as PageCopy & Dependencies
			return { blocks, components, files, page: pageCopy }
		})
	return writeClipboardPayload(payload, "Page copied")
}

export function copyBlocks(e: ClipboardEvent) {
	if (!isRootSelected()) {
		copySelectedBlocks(e)
		return
	}
	e.preventDefault()
	dialog.confirm({
		title: "Copy entire page?",
		message:
			"Do you want to copy the entire page including its data sources, variables and script along with its blocks?",
		actions: [
			{
				label: "No, just blocks",
				onClick: ({ close }) => {
					close()
					return writeClipboardPayload(
						Promise.resolve({ blocks: getSelectedBlockCopies(), source: getClipboardSource() }),
					)
				},
			},
			{
				label: "Yes",
				variant: "solid",
				onClick: ({ close }) => {
					close()
					return copyEntirePage()
				},
			},
		],
	})
}

export function copySelectedBlocks(e: ClipboardEvent) {
	const blocks = getSelectedBlockCopies()
	if (!blocks.length) return
	e.preventDefault()
	const source = getClipboardSource()

	if (!usesComponents(blocks) && !usesPageData(blocks)) {
		setClipboardData({ blocks, source }, e, CLIPBOARD_FORMAT)
		return
	}
	void writeClipboardPayload(
		fetchDependencies(blocks).then((dependencies) => ({ blocks, source, ...dependencies })),
	)
}

export function pasteBlocks(e: ClipboardEvent): boolean {
	const payload = getClipboardPayload(e)
	if (!payload) return false
	e.preventDefault()
	if (payload.page) {
		handlePastePage(payload)
	} else {
		void pasteCopiedBlocks(payload)
	}
	return true
}

function getClipboardSource(): ClipboardSource {
	const store = useStudioStore()
	const page = store.activePage!
	return {
		origin: window.location.origin,
		app: store.activeApp!.name,
		page: page.name,
		hasPageScript: Boolean(page.script?.trim()) || hasCompiledPageScript(page.name),
	}
}

function shouldWarnAboutExcludedPageScript(source?: ClipboardSource): boolean {
	if (source?.hasPageScript !== true) return false
	const store = useStudioStore()
	const isSamePage =
		source.origin === window.location.origin &&
		source.app === store.activeApp?.name &&
		source.page === store.activePage?.name
	return !isSamePage
}

async function pasteCopiedBlocks(payload: ClipboardPayload) {
	await createMissingDependencies(payload)
	const undoPaste = insertBlocks(payload.blocks)
	if (!undoPaste || !shouldWarnAboutExcludedPageScript(payload.source)) return

	toast.warning("Page script wasn't included", {
		duration: Infinity,
		action: {
			label: "Undo Paste",
			onClick: undoPaste,
		},
	})
}

function getSelectedBlockCopies(): BlockOptions[] {
	return useCanvasStore().activeCanvas?.selectedBlocks.map((block) => getBlockCopyWithoutParent(block)) || []
}

function getClipboardPayload(e: ClipboardEvent): ClipboardPayload | null {
	let data = e.clipboardData?.getData(CLIPBOARD_FORMAT) || ""
	if (!data) {
		const text = e.clipboardData?.getData("text/plain") || ""
		if (!text.startsWith(CLIPBOARD_PREFIX)) return null
		data = text.slice(CLIPBOARD_PREFIX.length)
	}
	if (!isJSONString(data)) return null

	const payload = JSON.parse(data)
	return payload && Array.isArray(payload.blocks) && payload.blocks.length ? payload : null
}

function writeClipboardPayload(payload: Promise<ClipboardPayload>, successMessage?: string): Promise<void> {
	const text = payload.then((value) => CLIPBOARD_PREFIX + JSON.stringify(value))
	let write: Promise<void>

	try {
		if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined") {
			write = text.then(writeClipboardTextFallback)
		} else {
			const blob = text.then((value) => new Blob([value], { type: "text/plain" }))
			write = navigator.clipboard.write([new ClipboardItem({ "text/plain": blob })])
		}
	} catch (error) {
		write = Promise.reject(error)
	}

	return write
		.then(() => {
			if (successMessage) toast.success(successMessage)
		})
		.catch((error) => {
			console.error("Failed to copy Studio blocks", error)
			toast.error("Could not copy to the clipboard")
		})
}

function writeClipboardTextFallback(text: string) {
	const textarea = document.createElement("textarea")
	textarea.value = text
	textarea.style.position = "fixed"
	textarea.style.opacity = "0"
	document.body.appendChild(textarea)
	textarea.select()
	const copied = document.execCommand("copy")
	textarea.remove()
	if (!copied) throw new Error("The browser denied clipboard access")
}

function isRootSelected() {
	const selected = useCanvasStore().activeCanvas?.selectedBlocks || []
	return selected.length === 1 && selected[0].isRoot()
}

function usesComponents(blocks: BlockOptions[]): boolean {
	return blocks.some(
		(block) =>
			block.isStudioComponent ||
			block.isCustomVueComponent ||
			usesComponents(block.children || []) ||
			Object.values(block.componentSlots || {}).some((slot) => usesComponents(slot.slotContent || [])),
	)
}

function usesPageData(blocks: BlockOptions[]): boolean {
	const codeStore = useCodeStore()
	const names = [...Object.keys(codeStore.resources), ...Object.keys(codeStore.variables)]
	const text = JSON.stringify(blocks)
	return names.some((name) => new RegExp(`\\b${name}\\b`).test(text))
}

async function fetchDependencies(blocks: BlockOptions[]): Promise<Dependencies> {
	const page = useStudioStore().activePage!
	const response = await studioPages.runDocMethod.submit({
		name: page.name,
		method: "get_dependencies",
		blocks,
	})
	return response.message
}

async function createMissingDependencies(payload: ClipboardPayload) {
	const { components, files, resources, variables } = payload
	if (![components, files, resources, variables].some((list) => list?.length)) return
	const store = useStudioStore()
	await call("studio.studio.doctype.studio_page.studio_page.create_missing_dependencies", {
		app_name: store.activeApp!.name,
		page_name: store.activePage!.name,
		components,
		files,
		resources,
		variables,
	})
	if (files?.length) await store.setCustomComponents()
	if (resources?.length || variables?.length) {
		await store.refreshActivePageModified()
		await store.setPageData(store.activePage!)
	}
}

function handlePastePage(payload: ClipboardPayload) {
	const store = useStudioStore()
	const copy = {
		...payload.page!,
		blocks: payload.blocks,
		components: payload.components,
		files: payload.files,
	}
	dialog.confirm({
		title: "Pasting a page!",
		message:
			"You are about to paste a page with data sources, variables, and scripts. Do you want to create a new page, or update the current one?",
		actions: [
			{ label: "Create new page", onClick: () => store.pastePage(copy) },
			{
				label: "Replace current page",
				variant: "solid",
				onClick: () => store.pastePage(copy, store.activePage?.name),
			},
		],
	})
}

function insertBlocks(blocks: BlockOptions[]): (() => void) | undefined {
	const canvasStore = useCanvasStore()
	const canvas = canvasStore.activeCanvas
	if (!canvas) return
	let insertedBlocks: Block[] = []

	if (canvas.selectedBlocks.length && blocks[0].componentId !== "root") {
		let parentBlock = canvas.selectedBlocks[0]
		const slotName = canvas.selectedSlot?.slotName
		while (parentBlock && !parentBlock.canHaveChildren()) {
			parentBlock = parentBlock.getParentBlock() as Block
		}
		insertedBlocks = blocks.map((block) => {
			if (slotName) {
				block.parentSlotName = slotName
			} else {
				delete block.parentSlotName
			}
			return parentBlock.addChild(getBlockCopy(block), null)
		})
	} else {
		const parentBlock = canvas.getRootBlock()
		const firstBlock = getBlockInstance(blocks[0])
		if (canvasStore.editingMode === "page" && firstBlock.isRoot() && canvas.rootComponent) {
			canvas.setRootBlock(firstBlock)
			return () => {
				if (useCanvasStore().activeCanvas === canvas && canvas.getRootBlock() === firstBlock) {
					canvas.setRootBlock(parentBlock)
				}
			}
		}
		insertedBlocks = blocks.map((block) => parentBlock.addChild(block))
	}

	return () => {
		if (useCanvasStore().activeCanvas !== canvas) return
		insertedBlocks.forEach((block) => block.deleteBlock())
		canvas.clearSelection()
	}
}
