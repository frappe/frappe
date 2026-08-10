<template>
	<div class="flex w-full flex-col gap-2">
		<InputLabel v-if="label">{{ label }}</InputLabel>

		<div role="radiogroup" aria-label="Active tab" class="flex flex-col gap-2">
			<div v-for="tab in tabs" :key="tab.navItem.componentId" class="flex items-center gap-2">
				<button
					class="flex size-4 flex-none items-center justify-center"
					:title="isActive(tab) ? 'Active tab' : 'Make active'"
					@click="activate(tab.value)"
					role="radio"
					:aria-checked="isActive(tab) ? 'true' : 'false'"
				>
					<span
						class="size-[5px] rounded-full"
						:class="isActive(tab) ? 'bg-surface-gray-7' : 'bg-surface-gray-3'"
					></span>
				</button>
				<Input
					class="flex-1"
					hideClearButton
					placeholder="Label"
					:modelValue="tab.label"
					:disabled="!tab.labelBlock"
					@update:modelValue="(value: string) => updateLabel(tab, value)"
				/>
				<Input
					hideClearButton
					placeholder="value"
					title="Tab value — the identity pairing the nav item with its panel"
					:modelValue="tab.value"
					@update:modelValue="(value: string) => renameValue(tab, value)"
				/>
				<Button
					class="flex-shrink-0 text-xs"
					variant="ghost"
					icon="lucide-x"
					title="Remove tab"
					@click="removeTab(tab)"
				/>
			</div>

			<Button variant="outline" class="w-full" icon-left="plus" @click="addTab">Add Tab</Button>
		</div>

		<!-- nav items and panels drifted (hand-edited values); pairing is by `value` -->
		<div v-if="mismatch.length" class="flex items-center gap-1.5 text-xs text-ink-amber-6">
			<span class="size-[5px] flex-none rounded-full bg-surface-amber-3"></span>
			{{ mismatch.join(" · ") }}
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button, toast } from "frappe-ui"
import Input from "@/components/Input.vue"
import InputLabel from "@/components/InputLabel.vue"
import Block from "@/utils/block"
import { navItem, settingsPanel, tabBlockName } from "@/utils/blockTemplate/familyTemplates"

const props = defineProps<{ block: Block; label?: string }>()

type TabEntry = {
	navItem: Block
	labelBlock: Block | null
	panel: Block | null
	value: string
	label: string
}

// A tab lives in two places — a SettingsNavItem in the sidebar and a SettingsPanel
// with the same `value` under content — managed together so they never drift.
const tabs = computed<TabEntry[]>(() =>
	navItems.value.map((item) => {
		const value = String(item.getProp("value") ?? "")
		const labelBlock =
			item.getChildrenAndSlotContent().find((child) => child.componentName === "TextBlock") || null
		return {
			navItem: item,
			labelBlock,
			panel: panels.value.find((panel) => panel.getProp("value") === value) || null,
			value,
			label: String(labelBlock?.getProp("text") ?? value),
		}
	}),
)

function addTab() {
	const parent = navParent.value
	if (!parent || !contentBlock.value) return
	const number = nextTabNumber()
	const value = `tab-${number}`
	const label = `Tab ${number}`
	parent.addChild(navItem(value, label), null, false)
	contentBlock.value.addChild(settingsPanel(value, label, "", []), null, false)
	activate(value)
}

function removeTab(tab: TabEntry) {
	const wasActive = isActive(tab)
	tab.navItem.getParentBlock()?.removeChild(tab.navItem)
	tab.panel?.getParentBlock()?.removeChild(tab.panel)
	if (wasActive) {
		activate(tabs.value[0]?.value ?? "")
	}
}

function updateLabel(tab: TabEntry, value: string) {
	syncBlockNames(tab, value)
	syncPanelTitle(tab, value)
	tab.labelBlock?.setProp("text", value)
}

// only while the title still mirrors the label — a hand-edited (or cleared) title stays
function syncPanelTitle(tab: TabEntry, label: string) {
	const header = tab.panel
		?.getChildrenAndSlotContent()
		.find((child) => child.componentName === "SettingsHeader")
	if (header?.getProp("title") === tab.label) header.setProp("title", label)
}

// layer names like "ProfileNavItem"/"ProfilePanel" follow the label,
// unless the block was renamed by hand in the layers panel
function syncBlockNames(tab: TabEntry, label: string) {
	renameBlock(tab.navItem, tab.label, label, "NavItem")
	renameBlock(tab.panel, tab.label, label, "Panel")
}

function renameBlock(block: Block | null, oldLabel: string, newLabel: string, suffix: "NavItem" | "Panel") {
	if (!block) return
	const isAutoNamed = !block.blockName || block.blockName === tabBlockName(oldLabel, suffix)
	if (isAutoNamed) block.blockName = tabBlockName(newLabel, suffix)
}

function renameValue(tab: TabEntry, next: string) {
	next = next.trim()
	if (!next || next === tab.value) return
	if (tabs.value.some((other) => other.value === next)) {
		toast.warning(`A tab with value "${next}" already exists`)
		return
	}
	const wasActive = isActive(tab)
	if (!tab.labelBlock) syncBlockNames(tab, next) // label falls back to value
	tab.navItem.setProp("value", next)
	tab.panel?.setProp("value", next)
	if (wasActive) {
		activate(next)
	}
}

function activate(value: string) {
	props.block.setProp("tab", value)
}

function isActive(tab: TabEntry) {
	return props.block.getProp("tab") === tab.value
}

function nextTabNumber() {
	const values = new Set(tabs.value.map((tab) => tab.value))
	let number = tabs.value.length + 1
	while (values.has(`tab-${number}`)) number++
	return number
}

const mismatch = computed(() => {
	const problems: string[] = []
	const unpaired = tabs.value.filter((tab) => !tab.panel).length
	if (unpaired) {
		problems.push(`${unpaired} nav item${unpaired === 1 ? "" : "s"} without a matching panel`)
	}
	const navValues = new Set(tabs.value.map((tab) => tab.value))
	const orphans = panels.value.filter((panel) => !navValues.has(String(panel.getProp("value") ?? "")))
	if (orphans.length) {
		problems.push(`${orphans.length} panel${orphans.length === 1 ? "" : "s"} without a nav item`)
	}
	return problems
})

const sidebarBlock = computed(
	() => props.block.children.find((child) => child.componentName === "SettingsSidebar") || null,
)

const contentBlock = computed(
	() => props.block.children.find((child) => child.componentName === "SettingsContent") || null,
)

// nav items sit directly in the sidebar or inside nav groups
const navItems = computed(() => {
	const items: Block[] = []
	const collect = (blocks: Block[]) => {
		blocks.forEach((child) => {
			if (child.componentName === "SettingsNavItem") items.push(child)
			if (child.componentName === "SettingsNavGroup") collect(child.getChildrenAndSlotContent())
		})
	}
	if (sidebarBlock.value) collect(sidebarBlock.value.getChildrenAndSlotContent())
	return items
})

// new nav items go where the last existing one sits (its group), else the sidebar
const navParent = computed(() => navItems.value.at(-1)?.getParentBlock() || sidebarBlock.value)

const panels = computed(() =>
	contentBlock.value
		? contentBlock.value
				.getChildrenAndSlotContent()
				.filter((child) => child.componentName === "SettingsPanel")
		: [],
)
</script>
