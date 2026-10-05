<template>
	<div class="flex min-h-screen flex-col gap-4 bg-surface-gray-1 p-6">
		<div class="flex flex-wrap items-end gap-3">
			<Select v-model="scenario" label="Canvas state" :options="scenarioOptions" />
			<Select v-model="width" label="Container width" :options="widthOptions" />
		</div>
		<div
			class="overflow-hidden rounded border border-outline-gray-2 bg-surface-base transition-[width]"
			:style="{ width, height: '560px', maxWidth: '100%' }"
		>
			<AutomationCanvas
				:nodes="activeSample.nodes"
				:edges="activeSample.edges"
				:start-options="startOptions"
				:block-options="blockOptions"
				:selected-id="activeSample.selectedId"
				:dim-unselected="activeSample.dimUnselected"
				:can-delete="Boolean(activeSample.selectedId)"
				:can-undo="true"
				:readonly="activeSample.readonly"
				@select="lastEvent = `Selected ${$event}`"
				@pick-start="lastEvent = `Picked start ${$event}`"
				@add-node="
					lastEvent = `Add ${$event.value} after ${$event.afterId || 'start'}${
						$event.branch ? ` on ${$event.branch}` : ''
					}`
				"
				@request-remove="lastEvent = `Remove ${$event}`"
				@run-branch="lastEvent = `Run ${$event.arm.key} of ${$event.nodeId}`"
				@undo="lastEvent = 'Undo'"
				@redo="lastEvent = 'Redo'"
			/>
		</div>
		<div class="text-p-sm text-ink-gray-6">{{ lastEvent || "Interact with the canvas" }}</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Select } from "frappe-ui";
import AutomationCanvas from "../AutomationCanvas.vue";
import type {
	AutomationCanvasEdge,
	AutomationCanvasNode,
	AutomationCanvasNodeData,
	AutomationCanvasOptionGroup,
} from "../types";

interface Sample {
	nodes: AutomationCanvasNode[];
	edges: AutomationCanvasEdge[];
	selectedId?: string;
	dimUnselected?: boolean;
	readonly?: boolean;
}

const COLUMN = 300;
const BRANCH_OFFSET = 108;

const scenario = ref("empty");
const width = ref("960px");
const lastEvent = ref("");
const scenarioOptions = [
	{ label: "Empty start", value: "empty" },
	{ label: "Linear flow", value: "linear" },
	{ label: "Branched with empty arm", value: "branched" },
	{ label: "Branches ready to rejoin", value: "rejoin" },
	{ label: "Inspecting a node", value: "selected" },
	{ label: "Error and incomplete nodes", value: "error" },
	{ label: "Trial run", value: "trial" },
	{ label: "Read-only flow", value: "readonly" },
];
const widthOptions = [
	{ label: "Wide · 960 px", value: "960px" },
	{ label: "Narrow · 420 px", value: "420px" },
];

const startOptions: AutomationCanvasOptionGroup[] = [
	{
		group: "Records",
		options: [
			{
				value: "created",
				label: "Record is created",
				description: "Start whenever a new record is created.",
				icon: "lucide-play",
				tone: "blue",
			},
		],
	},
];
const blockOptions: AutomationCanvasOptionGroup[] = [
	{
		group: "Flow",
		options: [
			{
				value: "wait",
				label: "Wait",
				description: "Pause for a fixed time.",
				icon: "lucide-timer",
				tone: "amber",
			},
			{
				value: "if",
				label: "If / Else",
				description: "Split into two arms.",
				icon: "lucide-git-branch",
				tone: "green",
			},
		],
	},
	{
		group: "Actions",
		options: [
			{ value: "email", label: "Send email", icon: "lucide-mail", tone: "violet" },
			{ value: "assign", label: "Assign to user", icon: "lucide-user-plus", tone: "violet" },
		],
	},
];

const samples: Record<string, Sample> = {
	empty: { nodes: [emptyStart()], edges: [] },
	linear: linearSample(),
	branched: branchedSample(),
	rejoin: rejoinSample(),
	selected: { ...linearSample(), selectedId: "email", dimUnselected: true },
	error: errorSample(),
	trial: trialSample(),
	readonly: { ...rejoinSample(), readonly: true },
};
const activeSample = computed(() => samples[scenario.value]);

function emptyStart() {
	return node("start", 0, 0, {
		kicker: "Trigger",
		label: "Start from scratch",
		detail: "Pick initial trigger",
		start: true,
		empty: true,
	});
}

function startNode() {
	return node("start", 0, 0, {
		kicker: "Trigger",
		label: "Record is created",
		detail: "on CRM Lead",
		icon: "lucide-play",
		tone: "blue",
		start: true,
	});
}

function linearSample(): Sample {
	const nodes = [
		startNode(),
		node("email", COLUMN, 0, emailData()),
		node("wait", COLUMN * 2, 0, waitData({ terminal: true })),
	];
	return { nodes, edges: chainEdges(nodes) };
}

function errorSample(): Sample {
	const nodes = [
		startNode(),
		node("email", COLUMN, 0, { ...emailData(), error: true }),
		node("wait", COLUMN * 2, 0, {
			...waitData({ terminal: true }),
			label: "Wait",
			detail: undefined,
			incomplete: "Set how long to wait",
		}),
	];
	return { nodes, edges: chainEdges(nodes) };
}

function branchedSample(): Sample {
	const start = startNode();
	const condition = conditionNode({ arms: [{ key: "Else", label: "Otherwise" }] });
	const action = node("qualified-email", COLUMN * 2, -BRANCH_OFFSET, {
		...emailData("Send qualified email"),
		terminal: true,
	});
	return {
		nodes: [start, condition, action],
		edges: [edge(start, condition), edge(condition, action, "If yes")],
	};
}

function rejoinSample(): Sample {
	const start = startNode();
	const condition = conditionNode({ canContinue: true });
	const yes = node("qualified-email", COLUMN * 2, -BRANCH_OFFSET, {
		...emailData("Send qualified email"),
	});
	const no = node("assign", COLUMN * 2, BRANCH_OFFSET, assignData());
	return {
		nodes: [start, condition, yes, no],
		edges: [
			edge(start, condition),
			edge(condition, yes, "If yes"),
			edge(condition, no, "Otherwise"),
		],
	};
}

function trialSample(): Sample {
	const start = { ...startNode(), data: { ...startNode().data, status: "Success" as const } };
	const condition = conditionNode({
		status: "Success",
		forced: true,
		retryArms: [{ key: "Else", label: "Otherwise" }],
	});
	const yes = node("qualified-email", COLUMN * 2, -BRANCH_OFFSET, {
		...emailData("Send qualified email"),
		status: "Failed",
	});
	const no = node("assign", COLUMN * 2, BRANCH_OFFSET, {
		...assignData(),
		status: "Skipped",
		dimmed: true,
	});
	const wait = node("wait", COLUMN * 3, -BRANCH_OFFSET, {
		...waitData({ terminal: true }),
		status: "running",
	});
	return {
		nodes: [start, condition, yes, no, wait],
		edges: [
			edge(start, condition),
			edge(condition, yes, "If yes"),
			edge(condition, no, "Otherwise"),
			edge(yes, wait),
		],
		readonly: true,
	};
}

function conditionNode(data: Partial<AutomationCanvasNodeData>) {
	return node("condition", COLUMN, 0, {
		kicker: "Condition",
		label: "Status is Qualified",
		detail: "Lead status equals Qualified",
		icon: "lucide-git-branch",
		tone: "green",
		branching: true,
		...data,
	});
}

function emailData(label = "Send welcome email"): AutomationCanvasNodeData {
	return {
		kicker: "Action",
		label,
		detail: "To the lead's email, using the Welcome template",
		icon: "lucide-mail",
		tone: "violet",
	};
}

function assignData(): AutomationCanvasNodeData {
	return {
		kicker: "Action",
		label: "Assign to sales",
		detail: "Round robin across the Sales team",
		icon: "lucide-user-plus",
		tone: "violet",
	};
}

function waitData(data: Partial<AutomationCanvasNodeData> = {}): AutomationCanvasNodeData {
	return {
		kicker: "Wait",
		label: "Wait 2 hours",
		detail: "Then continue",
		icon: "lucide-timer",
		tone: "amber",
		...data,
	};
}

function node(id: string, x: number, y: number, data: AutomationCanvasNodeData) {
	return { id, position: { x, y }, data };
}

function edge(
	source: AutomationCanvasNode,
	target: AutomationCanvasNode,
	label?: string
): AutomationCanvasEdge {
	return { id: `${source.id}->${target.id}`, source: source.id, target: target.id, label };
}

function chainEdges(nodes: AutomationCanvasNode[]) {
	return nodes.slice(1).map((target, index) => edge(nodes[index], target));
}
</script>
