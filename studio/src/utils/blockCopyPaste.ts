import { dialog, toast, call } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import useCodeStore from "@/stores/codeStore"
import { studioPages } from "@/data/studioPages"
import { getBlockCopy, getBlockCopyWithoutParent, isJSONString } from "@/utils/serializer"
import { setClipboardData } from "@/utils/helpers"
import Block from "@/utils/block"
import type { BlockOptions } from "@/types"

const CLIPBOARD_FORMAT = "studio-copied-blocks"

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

interface ClipboardPayload extends Partial<Dependencies> {
	blocks: BlockOptions[]
	page?: PageCopy
}

let pending: ClipboardPayload | null = null
let blocksOnly = false

export async function copyEntirePage() {
	const page = useStudioStore().activePage
	const root = useCanvasStore().activeCanvas?.getRootBlock()
	if (!page || !root) return
	const blocks = [getBlockCopyWithoutParent(root)]
	const response = await studioPages.runDocMethod.submit({ name: page.name, method: "get_copy", blocks })
	const { components, files, ...pageCopy } = response.message as PageCopy & Dependencies
	writePending({ blocks, components, files, page: pageCopy })
}

export function copyBlocks(e: ClipboardEvent) {
	if (pending || blocksOnly || !isRootSelected()) {
		copySelectedBlocks(e)
		return
	}
	e.preventDefault()
	dialog.confirm({
		title: "Copy entire page?",
		message: "Copy the page's data sources, variables and script along with its blocks?",
		actions: [
			{
				label: "Just the blocks",
				onClick: ({ close }) => {
					close()
					copyBlocksOnly()
				},
			},
			{
				label: "Copy page",
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
	if (pending) {
		e.preventDefault()
		setClipboardData(pending, e, CLIPBOARD_FORMAT)
		if (pending.page) toast.success("Page copied")
		return
	}

	const canvas = useCanvasStore().activeCanvas
	const blocks = canvas?.selectedBlocks.map((block) => getBlockCopyWithoutParent(block)) || []
	if (!blocks.length) return
	e.preventDefault()

	if (!usesComponents(blocks) && !usesPageData(blocks)) {
		setClipboardData({ blocks }, e, CLIPBOARD_FORMAT)
		return
	}
	fetchDependencies(blocks).then((dependencies) => writePending({ blocks, ...dependencies }))
}

export function pasteBlocks(e: ClipboardEvent): boolean {
	const data = e.clipboardData?.getData(CLIPBOARD_FORMAT)
	if (!data || !isJSONString(data)) return false

	const payload = JSON.parse(data) as ClipboardPayload
	if (payload.page) {
		handlePastePage(payload)
	} else {
		createMissingDependencies(payload).then(() => insertBlocks(payload.blocks))
	}
	return true
}

function writePending(payload: ClipboardPayload) {
	pending = payload
	document.execCommand("copy")
	pending = null
}

function copyBlocksOnly() {
	blocksOnly = true
	document.execCommand("copy")
	blocksOnly = false
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
	const response = await studioPages.runDocMethod.submit({ name: page.name, method: "get_dependencies", blocks })
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
	const copy = { ...payload.page!, blocks: payload.blocks, components: payload.components, files: payload.files }
	dialog.confirm({
		title: "Paste page",
		message:
			"This copy includes the page's data sources, variables and script. Create a new page from it, or replace the contents of the current page?",
		actions: [
			{ label: "Replace current page", onClick: () => store.pastePage(copy, store.activePage?.name) },
			{ label: "Create new page", variant: "solid", onClick: () => store.pastePage(copy) },
		],
	})
}

function insertBlocks(blocks: BlockOptions[]) {
	const canvasStore = useCanvasStore()
	const canvas = canvasStore.activeCanvas
	if (!canvas) return

	if (canvas.selectedBlocks.length && blocks[0].componentId !== "root") {
		let parentBlock = canvas.selectedBlocks[0]
		const slotName = canvas.selectedSlot?.slotName
		while (parentBlock && !parentBlock.canHaveChildren()) {
			parentBlock = parentBlock.getParentBlock() as Block
		}
		blocks.forEach((block) => {
			if (slotName) {
				block.parentSlotName = slotName
			} else {
				delete block.parentSlotName
			}
			parentBlock.addChild(getBlockCopy(block), null)
		})
	} else {
		canvasStore.pushBlocks(blocks)
	}
}
