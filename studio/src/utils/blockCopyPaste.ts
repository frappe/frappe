import { dialog, toast } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
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
	components: Record<string, any>[]
}

interface ClipboardPayload {
	blocks: BlockOptions[]
	page?: PageCopy
}

let pendingPageCopy: PageCopy | null = null
let blocksOnly = false

export async function copyEntirePage() {
	const page = useStudioStore().activePage
	const root = useCanvasStore().activeCanvas?.getRootBlock()
	if (!page || !root) return
	const response = await studioPages.runDocMethod.submit({
		name: page.name,
		method: "get_copy",
		blocks: [getBlockCopyWithoutParent(root)],
	})
	pendingPageCopy = response.message as PageCopy
	document.execCommand("copy")
	pendingPageCopy = null
}

export function copyBlocks(e: ClipboardEvent) {
	if (pendingPageCopy || blocksOnly || !isRootSelected()) {
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
	const canvas = useCanvasStore().activeCanvas
	if (!canvas) return
	const blocks = pendingPageCopy ? [canvas.getRootBlock()] : canvas.selectedBlocks
	if (!blocks.length) return
	e.preventDefault()

	const payload: ClipboardPayload = { blocks: blocks.map((block) => getBlockCopyWithoutParent(block)) }
	if (pendingPageCopy) {
		payload.page = pendingPageCopy
		toast.success("Page copied")
	}
	setClipboardData(payload, e, CLIPBOARD_FORMAT)
}

export function pasteBlocks(e: ClipboardEvent): boolean {
	const data = e.clipboardData?.getData(CLIPBOARD_FORMAT)
	if (!data || !isJSONString(data)) return false

	const payload = JSON.parse(data) as ClipboardPayload
	if (payload.page) {
		askWhereToPastePage(payload.page, payload.blocks)
	} else {
		insertBlocks(payload.blocks)
	}
	return true
}

function askWhereToPastePage(page: PageCopy, blocks: BlockOptions[]) {
	const store = useStudioStore()
	const copy = { ...page, blocks }
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

function copyBlocksOnly() {
	blocksOnly = true
	document.execCommand("copy")
	blocksOnly = false
}

function isRootSelected() {
	const selected = useCanvasStore().activeCanvas?.selectedBlocks || []
	return selected.length === 1 && selected[0].isRoot()
}
