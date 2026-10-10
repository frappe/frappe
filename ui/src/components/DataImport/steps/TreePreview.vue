<template>
	<div v-if="treePreview" class="flex w-full min-w-0 flex-col gap-2">
		<Alert
			v-if="!nodes.length"
			theme="amber"
			:title="t('No valid tree nodes found in the import file.')"
		/>
		<template v-else>
			<Alert
				v-if="warningCount"
				theme="amber"
				:title="
					warningCount === 1
						? t('1 warning found.')
						: t('{0} warnings found.', [warningCount])
				"
				:description="t('See warning icons on nodes below or check the Warnings section.')"
			/>
			<div class="flex items-center justify-between gap-2">
				<TextInput
					v-model="query"
					class="min-w-0 max-w-lg flex-1"
					type="search"
					autocomplete="off"
					:placeholder="t('Filter nodes')"
				>
					<template #prefix>
						<span class="lucide-search size-4 text-ink-gray-6" />
					</template>
				</TextInput>
				<div class="inline-flex shrink-0 items-center gap-1">
					<Button
						v-if="!readonly && hasEditedNodes"
						variant="outline"
						theme="red"
						:label="t('Reset all')"
						:disabled="saving"
						@click="resetAll"
					/>
					<Button
						variant="outline"
						:label="t('Expand all')"
						:disabled="allExpanded"
						@click="expanded = [...branchKeys]"
					/>
					<Button
						variant="outline"
						:label="t('Collapse all')"
						:disabled="allCollapsed"
						@click="expanded = []"
					/>
				</div>
			</div>

			<TooltipProvider>
				<div
					class="flex flex-col overflow-hidden rounded-5 border border-outline-gray-2 bg-surface-base"
				>
					<div class="h-[min(360px,48vh)] overflow-auto px-4 py-2">
						<Tree v-model:expanded="expanded" :nodes="treeNodes">
							<template #item="{ node, level, expanded: open }">
								<div
									data-tree-row
									:data-row-number="node.key"
									:class="[
										'-mx-1.5 flex h-full min-w-0 flex-1 cursor-pointer items-center gap-2 rounded-5 px-1.5 text-base hover:bg-surface-gray-2',
										selectedRow === node.key && 'bg-surface-gray-3',
									]"
									@click="select(node.key as number)"
								>
									<span
										:class="[
											'flex min-w-0 flex-1 items-center gap-1',
											level === 1 && 'font-medium',
										]"
									>
										<span
											:class="[
												'inline-flex size-4 shrink-0 items-center justify-center text-ink-gray-6',
												!node.expandable && 'invisible',
												open
													? 'lucide-chevron-down'
													: 'lucide-chevron-right',
											]"
											aria-hidden="true"
										/>
										<span
											:class="[
												'min-w-0 truncate',
												node.orphan
													? 'text-ink-orange-7'
													: 'text-ink-gray-8',
											]"
											>{{ node.label }}</span
										>
									</span>
									<span class="flex shrink-0 items-center gap-2 ps-2 text-sm">
										<span class="flex w-16 shrink-0 justify-end">
											<Badge
												v-if="isEdited(info(node))"
												theme="gray"
												size="sm"
												:label="t('Edited')"
											/>
										</span>
										<span v-if="!readonly" class="flex w-4 shrink-0">
											<Tooltip
												v-if="info(node).warnings?.length"
												:text="warningText(info(node))"
											>
												<span
													data-tree-warning
													class="lucide-triangle-alert size-4 text-ink-amber-6"
												/>
											</Tooltip>
										</span>
										<span
											v-if="tree.orphans.size"
											class="w-20 shrink-0 text-ink-gray-6"
										>
											<template v-if="node.orphan"
												>({{ t("unlinked") }})</template
											>
										</span>
										<span
											v-if="canEditNode"
											class="flex w-24 shrink-0 justify-end"
											@click.stop
										>
											<Dropdown
												align="end"
												:options="
													menuRow === node.key
														? menuItems(info(node))
														: []
												"
												@update:open="(open) => open && (menuRow = node.key as number)"
											>
												<Button
													size="xs"
													variant="outline"
													icon-right="lucide-chevron-down"
													:label="t('Actions')"
													:disabled="saving"
												/>
											</Dropdown>
										</span>
									</span>
								</div>
							</template>
						</Tree>
					</div>
					<div
						class="flex shrink-0 items-center border-t border-outline-gray-2 bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-6"
					>
						<span class="whitespace-nowrap">{{
							totalNodes === 1
								? t("1 node")
								: t("Tree preview of {0} nodes", [totalNodes])
						}}</span>
					</div>
				</div>
			</TooltipProvider>
		</template>
	</div>
</template>

<script setup lang="ts">
import {
	Alert,
	Badge,
	Button,
	Dropdown,
	TextInput,
	Tooltip,
	TooltipProvider,
	Tree,
} from "frappe-ui";
import type { DropdownOption, TreeNode } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { cint, isImportComplete } from "../dataImport";
import { t } from "../translate";
import type { UseDataImport } from "../useDataImport";

/** One node of `tree_preview.nodes` from `get_preview_from_template`. */
type TreeNodeData = {
	id: string;
	label: string;
	parent: string | null;
	row_number: number;
	is_group: number;
	orig_parent: string | null;
	orig_is_group: number;
	orphan?: boolean;
	warnings?: string[];
};

const props = defineProps<{ dataImport: UseDataImport }>();
const emit = defineEmits<{ select: [rowNumber: number] }>();
const { doc, preview, saving } = props.dataImport;

const info = (node: TreeNode) => node.data as TreeNodeData;

const treePreview = computed(() => preview.value?.tree_preview);
const nodes = computed<TreeNodeData[]>(() => treePreview.value?.nodes ?? []);
const totalNodes = computed(() => treePreview.value?.total_nodes ?? nodes.value.length);
const editable = computed(() => Boolean(treePreview.value?.editable));
const isGroupEditable = computed(() => Boolean(treePreview.value?.is_group_editable));

const readonly = computed(() => isImportComplete(doc.value.status));
const canEditNode = computed(() => !readonly.value && (editable.value || isGroupEditable.value));
// A finished import keeps the tree for reference but drops its warnings.
const warningCount = computed(() =>
	readonly.value ? 0 : treePreview.value?.tree_warnings?.length ?? 0
);

/** Nodes in a parent cycle can't be reached from the roots, so they show at the top as unlinked. */
const tree = computed(() => {
	const byId = new Map(nodes.value.map((node) => [node.id, node]));
	const childrenOf = new Map<string, TreeNodeData[]>();
	const roots: TreeNodeData[] = [];
	for (const node of nodes.value) {
		if (node.orphan || !node.parent || !byId.has(node.parent)) roots.push(node);
		else childrenOf.set(node.parent, [...(childrenOf.get(node.parent) ?? []), node]);
	}

	const reachable = new Set<string>();
	const stack = roots.map((node) => node.id);
	while (stack.length) {
		const id = stack.pop()!;
		if (reachable.has(id)) continue;
		reachable.add(id);
		for (const child of childrenOf.get(id) ?? []) stack.push(child.id);
	}

	const orphans = new Set(nodes.value.filter((node) => node.orphan));
	for (const node of nodes.value) {
		if (reachable.has(node.id)) continue;
		orphans.add(node);
		roots.push(node);
		const siblings = childrenOf.get(node.parent!);
		if (siblings)
			childrenOf.set(
				node.parent!,
				siblings.filter((child) => child.id !== node.id)
			);
	}
	return { roots, childrenOf, orphans };
});

const branchKeys = computed(() => {
	const keys = new Set<number>();
	const walk = (list: TreeNodeData[]) => {
		for (const node of list) {
			const children = tree.value.childrenOf.get(node.id) ?? [];
			if (children.length) {
				keys.add(node.row_number);
				walk(children);
			}
		}
	};
	walk(tree.value.roots);
	return keys;
});

const expanded = ref<number[]>([]);
const query = ref("");
const selectedRow = ref<number | null>(null);
const menuRow = ref<number | null>(null);

// Like Desk, every change to the tree draws it again fully expanded with an empty filter.
watch(
	tree,
	() => {
		expanded.value = [...branchKeys.value];
		query.value = "";
	},
	{ immediate: true }
);

const openBranchCount = computed(
	() => expanded.value.filter((key) => branchKeys.value.has(key)).length
);
const allExpanded = computed(
	() => branchKeys.value.size > 0 && openBranchCount.value === branchKeys.value.size
);
const allCollapsed = computed(() => branchKeys.value.size > 0 && openBranchCount.value === 0);

/** Matches the label or the file's row number; ancestors of a match stay visible. */
function matches(node: TreeNodeData, q: string) {
	const rowQuery = q.replace(/^#/, "");
	return (
		(node.label || "").toLowerCase().includes(q) ||
		(!!rowQuery && String(node.row_number ?? "").includes(rowQuery))
	);
}

const treeNodes = computed(() => {
	const q = query.value.trim().toLowerCase();
	const build = (node: TreeNodeData): TreeNode | null => {
		const all = tree.value.childrenOf.get(node.id) ?? [];
		const children = all.map(build).filter((child): child is TreeNode => !!child);
		if (q && !matches(node, q) && !children.length) return null;
		return {
			key: node.row_number,
			label: node.label,
			children,
			data: node,
			orphan: tree.value.orphans.has(node),
			expandable: cint(node.is_group) || all.length > 0,
		};
	};
	return tree.value.roots.map(build).filter((node): node is TreeNode => !!node);
});

// Filtering opens every branch that still shows a node.
watch(query, (value) => {
	if (!value.trim()) return;
	const keys = new Set(expanded.value);
	const walk = (list: TreeNode[]) => {
		for (const node of list) {
			if (node.children?.length) {
				keys.add(node.key as number);
				walk(node.children);
			}
		}
	};
	walk(treeNodes.value);
	expanded.value = [...keys];
});

function select(rowNumber: number) {
	selectedRow.value = rowNumber;
	emit("select", rowNumber);
}

function warningText(node: TreeNodeData) {
	return (node.warnings ?? []).map((warning) => warning.replace(/<[^>]*>/g, "")).join(" ");
}

function isEdited(node: TreeNodeData) {
	return (
		(node.parent || null) !== (node.orig_parent || null) ||
		cint(node.is_group) !== cint(node.orig_is_group)
	);
}

const hasEditedNodes = computed(() => nodes.value.some(isEdited));
const hasChildren = (node: TreeNodeData) => nodes.value.some((n) => n.parent === node.id);

/** The node and everything under it; moving a node under any of these would make a cycle. */
function descendantIds(node: TreeNodeData) {
	const ids = new Set([node.id]);
	let frontier = [node.id];
	while (frontier.length) {
		const next: string[] = [];
		for (const parentId of frontier)
			for (const child of nodes.value)
				if (child.parent === parentId && !ids.has(child.id)) {
					ids.add(child.id);
					next.push(child.id);
				}
		frontier = next;
	}
	return ids;
}

function moveTargets(node: TreeNodeData): DropdownOption[] {
	const descendants = descendantIds(node);
	const targets: DropdownOption[] = nodes.value
		.filter(
			(n) =>
				cint(n.is_group) &&
				n.id !== node.id &&
				n.id !== node.parent &&
				!descendants.has(n.id)
		)
		.sort((a, b) => (a.label || "").localeCompare(b.label || ""))
		.map((n) => ({
			label: n.label,
			icon: "lucide-folder",
			onClick: () => moveTo(node, n.id),
		}));
	const items = [
		...(node.parent
			? [
					{
						label: t("Top level"),
						icon: "lucide-corner-left-up",
						onClick: () => moveTo(node, ""),
					},
			  ]
			: []),
		...targets,
	];
	return items.length ? items : [{ label: t("No available parents"), disabled: true }];
}

function menuItems(node: TreeNodeData) {
	const items: DropdownOption[] = [];
	if (editable.value)
		items.push({
			label: t("Move to…"),
			icon: "lucide-corner-up-right",
			submenu: moveTargets(node),
		});
	if (isGroupEditable.value && !cint(node.is_group))
		items.push({
			label: t("Mark as group"),
			icon: "lucide-folder",
			onClick: () => setGroup(node, 1),
		});
	if (isGroupEditable.value && cint(node.is_group) && !hasChildren(node))
		items.push({
			label: t("Mark as leaf"),
			icon: "lucide-file",
			onClick: () => setGroup(node, 0),
		});
	if (isEdited(node))
		items.push({
			label: t("Reset node"),
			icon: "lucide-rotate-ccw",
			theme: "red",
			onClick: () => resetNode(node),
		});
	return items.length ? items : [{ label: t("No actions available"), disabled: true }];
}

// Edits change the nodes in place so the tree redraws at once, then save the overrides.
function moveTo(node: TreeNodeData, parentId: string) {
	node.parent = parentId || null;
	node.orphan = false;
	persist();
}

function setGroup(node: TreeNodeData, isGroup: number) {
	node.is_group = isGroup;
	persist();
}

function restore(node: TreeNodeData) {
	node.parent = node.orig_parent || null;
	node.is_group = cint(node.orig_is_group);
	node.orphan = false;
}

function resetNode(node: TreeNodeData) {
	restore(node);
	persist();
}

function resetAll() {
	for (const node of nodes.value) if (isEdited(node)) restore(node);
	persist();
}

/** `tree_parent_overrides` is `{row_number: {parent, is_group}}`, only for what differs from the file. */
function persist() {
	const overrides: Record<number, { parent?: string; is_group?: number }> = {};
	for (const node of nodes.value) {
		const delta: { parent?: string; is_group?: number } = {};
		if ((node.parent || null) !== (node.orig_parent || null)) delta.parent = node.parent || "";
		if (cint(node.is_group) !== cint(node.orig_is_group)) delta.is_group = cint(node.is_group);
		if (Object.keys(delta).length) overrides[node.row_number] = delta;
	}
	const value = Object.keys(overrides).length ? JSON.stringify(overrides) : "";
	if ((doc.value.tree_parent_overrides || "") === value) return;
	doc.value.tree_parent_overrides = value;
	props.dataImport.save().catch(() => {});
}
</script>
