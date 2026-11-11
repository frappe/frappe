import { armLabels, isBranching } from "./workflowSteps";

export function workflowEdges(actions = []) {
	const edges = [];
	appendEdges(actions, [{ id: "trigger", label: null }], edges);
	return edges;
}

function appendEdges(nodes, sources, edges) {
	let tails = sources;
	nodes.forEach((node) => {
		connectSources(tails, node._id, edges);
		tails = isBranching(node)
			? appendBranchEdges(node, edges)
			: [{ id: node._id, label: null }];
	});
	return tails;
}

function connectSources(sources, target, edges) {
	sources.forEach(({ id, label }) => edges.push(edge(id, target, label)));
}

function appendBranchEdges(node, edges) {
	const labels = armLabels(node);
	return ["If", "Else"].flatMap((branch) =>
		appendEdges(node.children[branch], [{ id: node._id, label: labels[branch] }], edges)
	);
}

function edge(source, target, label) {
	return { id: `${source}->${target}:${label || ""}`, source, target, label };
}
