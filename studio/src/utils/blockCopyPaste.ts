import { dialog, toast, call } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import useCodeStore from "@/stores/codeStore"
import useComponentStore from "@/stores/componentStore"
import { studioPages } from "@/data/studioPages"
import { hasPageScript as hasCompiledPageScript } from "@/data/studioPageScripts"
import {
	showPasteConflictDialog,
	type PasteConflictChoice,
	type PasteConflictKind,
} from "@/components/PasteConflictDialog.vue"
import PasteWarningToast from "@/components/PasteWarningToast.vue"
import { getBlockCopy, getBlockCopyWithoutParent, getBlockInstance, isJSONString } from "@/utils/serializer"
import { setClipboardData } from "@/utils/helpers"
import Block from "@/utils/block"
import type { BlockOptions } from "@/types"

const CLIPBOARD_FORMAT = "studio-copied-blocks"
const CLIPBOARD_PREFIX = `${CLIPBOARD_FORMAT}:`
const DATA_SOURCE_DOCTYPE = "Studio Page Resource"

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

interface DataSourceClipboardPayload {
	doctype: typeof DATA_SOURCE_DOCTYPE
	resource_name: string
	[key: string]: any
}

interface PasteConflict {
	name: string
	existing: Record<string, any>
	copied: Record<string, any>
}

interface PasteConflicts {
	components?: PasteConflict[]
	resources?: PasteConflict[]
	variables?: PasteConflict[]
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
				onClick: () => {
					return writeClipboardPayload(
						Promise.resolve({ blocks: getSelectedBlockCopies(), source: getClipboardSource() }),
					)
				},
			},
			{
				label: "Yes",
				variant: "solid",
				onClick: () => {
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

export function copyDataSource(resource: Promise<Record<string, any> | undefined>, resourceName: string) {
	const text = resource.then((value) => {
		if (!value) throw new Error(`Could not find data source "${resourceName}"`)
		const definition = { ...value }
		delete definition.resource_id
		return JSON.stringify({ ...definition, doctype: DATA_SOURCE_DOCTYPE })
	})
	return writeClipboardText(text, `Data source "${resourceName}" copied`)
}

export function pasteDataSource(e: ClipboardEvent): boolean {
	const resource = getCopiedDataSource(e)
	if (!resource) return false
	e.preventDefault()
	void createDataSource(resource)
	return true
}

async function createDataSource(resource: DataSourceClipboardPayload) {
	const store = useStudioStore()
	const page = store.activePage
	if (!page) return

	try {
		const result = await call(
			"studio.studio.doctype.studio_page.copy_paste_handler.paste_data_source",
			{
				app_name: store.activeApp!.name,
				page_name: page.name,
				resource,
			},
		)
		if (store.activePage?.name !== page.name) return
		store.syncPageModified(result)
		await store.setPageData(page)
		toast.success(`Data source "${resource.resource_name}" created`)
	} catch (error: any) {
		toast.error(`Failed to create Data source "${resource.resource_name}"`, {
			description: error?.messages?.join(", ") || error?.message
		})
	}
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

function isPageScriptExcluded(source?: ClipboardSource): boolean {
	if (source?.hasPageScript !== true) return false
	const store = useStudioStore()
	const isSamePage =
		source.origin === window.location.origin &&
		source.app === store.activeApp?.name &&
		source.page === store.activePage?.name
	return !isSamePage
}

async function pasteCopiedBlocks(payload: ClipboardPayload) {
	let conflicts: PasteConflicts
	try {
		conflicts = await createMissingDependencies(payload)
	} catch (error: any) {
		toast.error("Could not paste blocks", {
			description: error?.messages?.join(", ") || error?.message,
			duration: 8000,
		})
		return
	}
	const removePastedBlocks = insertBlocks(payload.blocks)
	if (!removePastedBlocks) return

	if (hasPasteConflicts(conflicts)) {
		reviewPasteConflicts(payload, conflicts, removePastedBlocks)
		return
	}

	if (isPageScriptExcluded(payload.source)) {
		showPasteWarningToast(removePastedBlocks)
	}
}

function hasPasteConflicts(conflicts: PasteConflicts): boolean {
	return [conflicts.resources, conflicts.variables, conflicts.components].some((items) => items?.length)
}

function reviewPasteConflicts(
	payload: ClipboardPayload,
	conflicts: PasteConflicts,
	removePastedBlocks: () => void,
) {
	const pageScriptExcluded = isPageScriptExcluded(payload.source)

	showPasteConflictDialog(getPasteConflictChoices(conflicts), {
		onApply: async (choices) => {
			const copiedChoices = choices.filter(({ resolution }) => resolution === "copied")
			if (copiedChoices.length) {
				await createMissingDependencies(getCopiedDependencies(copiedChoices), true)
			}
		},
		onRemove: removePastedBlocks,
		warning: pageScriptExcluded
			? "The page script wasn't copied, so some references in these blocks may not work yet. Add required references from the source manually."
			: undefined,
	})
}

function getPasteConflictChoices(conflicts: PasteConflicts): Omit<PasteConflictChoice, "resolution">[] {
	const choices: Omit<PasteConflictChoice, "resolution">[] = []
	for (const kind of ["resources", "variables", "components"] as PasteConflictKind[]) {
		for (const [index, conflict] of (conflicts[kind] || []).entries()) {
			choices.push({ id: `${kind}:${conflict.name}:${index}`, kind, ...conflict })
		}
	}
	return choices
}

function getCopiedDependencies(choices: PasteConflictChoice[]): Partial<Dependencies> {
	const definitionsFor = (kind: PasteConflictKind) =>
		choices.filter((choice) => choice.kind === kind).map((choice) => choice.copied)
	return {
		components: definitionsFor("components"),
		resources: definitionsFor("resources"),
		variables: definitionsFor("variables"),
	}
}

function showPasteWarningToast(removePastedBlocks: () => void) {
	toast.custom(PasteWarningToast, {
		duration: 10000,
		componentProps: {
			onRevert: removePastedBlocks,
		},
		classes: {
			toast: "!w-auto !bg-transparent !p-0 !shadow-none",
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

function getCopiedDataSource(e: ClipboardEvent): DataSourceClipboardPayload | null {
	const text = e.clipboardData?.getData("text/plain") || ""
	if (!isJSONString(text)) return null
	const resource = JSON.parse(text)
	if (
		resource?.doctype !== DATA_SOURCE_DOCTYPE ||
		typeof resource !== "object" ||
		Array.isArray(resource) ||
		typeof resource.resource_name !== "string"
	) {
		return null
	}
	return resource
}

function writeClipboardPayload(payload: Promise<ClipboardPayload>, successMessage?: string): Promise<void> {
	const text = payload.then((value) => CLIPBOARD_PREFIX + JSON.stringify(value))
	return writeClipboardText(text, successMessage)
}

function writeClipboardText(text: Promise<string>, successMessage?: string): Promise<void> {
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
			console.error("Failed to copy to clipboard", error)
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
	return names.some((name) => name && text.includes(name))
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

async function createMissingDependencies(
	payload: Partial<Dependencies>,
	overwriteConflicts = false,
): Promise<PasteConflicts> {
	const { components, files, resources, variables } = payload
	if (![components, files, resources, variables].some((list) => list?.length)) return {}
	const store = useStudioStore()
	const pageName = store.activePage!.name
	const result = await call(
		"studio.studio.doctype.studio_page.copy_paste_handler.create_missing_dependencies",
		{
			app_name: store.activeApp!.name,
			page_name: pageName,
			components,
			files,
			resources,
			variables,
			overwrite_conflicts: overwriteConflicts,
		},
	)
	if (store.activePage?.name === pageName) store.syncPageModified(result)
	if (components?.length && overwriteConflicts) {
		await Promise.all(components.map(({ name }) => useComponentStore().reloadComponent(name)))
	}
	if (files?.length) await store.setCustomComponents()
	if (resources?.length || variables?.length) {
		await store.setPageData(store.activePage!)
	}
	return result.conflicts || {}
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
