import { __ } from "frappe/i18n";
import { runMethod } from "@framework/ui/api";
import { reactive } from "vue";

/**
 * Registered triggers, relationships, fields and actions, cached per DocType. A step targeting
 * a relationship alias needs the capabilities of that alias' DocType, not the flow's, so the
 * builder loads one entry per target it can reach.
 */
const cache = reactive({});
const pending = new Set();

/**
 * What this builder offers of an action's params, where it offers less than the framework
 * defines. A script step is pointed at a Server Script here; Python is written and reviewed
 * in the desk, where the roles that may author it live.
 */
const OFFERED_PARAMS = { RunScript: ["server_script"] };

export function capabilitiesFor(doctype) {
	return doctype ? cache[doctype] || null : null;
}

export async function loadCapabilities(doctype) {
	if (!doctype || cache[doctype] || pending.has(doctype)) return;
	pending.add(doctype);
	try {
		const { data } = await runMethod(
			"frappe.automation_engine.api.get_automation_capabilities",
			{ doctype },
			{ http: "GET" }
		);
		cache[doctype] = offeredHere(data);
	} finally {
		pending.delete(doctype);
	}
}

function offeredHere(capabilities) {
	return {
		...capabilities,
		actions: (capabilities.actions || []).map(offeredParams),
	};
}

function offeredParams(action) {
	const offered = OFFERED_PARAMS[action.action_type];
	if (!offered) return action;
	return {
		...action,
		params_schema: (action.params_schema || []).filter((param) =>
			offered.includes(param.fieldname)
		),
	};
}

export function relationshipDefinition(doctype, relationship) {
	return (capabilitiesFor(doctype)?.relationships || []).find(
		(item) => item.name === relationship
	);
}

export function actionSchema(doctype, actionType) {
	if (!actionType) return null;
	const scoped = (capabilitiesFor(doctype)?.actions || []).find(
		(a) => a.action_type === actionType
	);
	return scoped || anyActionSchema(actionType);
}

/** Action definitions are global; only their availability is scoped to a DocType. */
function anyActionSchema(actionType) {
	for (const capabilities of Object.values(cache)) {
		const match = (capabilities.actions || []).find((a) => a.action_type === actionType);
		if (match) return match;
	}
	return null;
}

/**
 * Every record alias a step may target: the trigger, the flow's predeclared relationship
 * aliases, and the destination aliases of steps that run earlier.
 */
export function aliasTargets(documentType, relationships = [], earlierSteps = []) {
	const targets = [{ alias: "trigger", doctype: documentType, label: __("Trigger record") }];
	relationships.forEach((item) => addRelationshipAlias(targets, item));
	earlierSteps.forEach((step) => addOutputAlias(targets, step));
	return targets;
}

function addRelationshipAlias(targets, item) {
	if (!item.alias || !item.relationship) return;
	const source = targets.find((target) => target.alias === (item.source || "trigger"));
	const definition = relationshipDefinition(source?.doctype, item.relationship);
	targets.push({
		alias: item.alias,
		doctype: item.target_doctype || resolvedTarget(definition),
		label: definition?.label || item.relationship,
		choices: definition?.target_doctypes || [],
	});
}

/**
 * A relationship may allow several DocTypes (a dynamic reference narrowed to a few). One
 * choice needs no asking; more than one stays unknown until the flow picks, because the
 * builder can't offer actions or fields without knowing which DocType it is dealing with.
 */
function resolvedTarget(definition) {
	if (definition?.target_doctype) return definition.target_doctype;
	const choices = definition?.target_doctypes || [];
	return choices.length === 1 ? choices[0] : null;
}

function addOutputAlias(targets, step) {
	if (!step.output_alias) return;
	const action = actionSchema(null, step.action_type);
	const declared = action?.output_schema?.destination_reference?.doctype;
	targets.push({
		alias: step.output_alias,
		doctype: (declared === "Dynamic" ? stepParams(step).doctype : declared) || null,
		label: __("Output of {0}", [step.step_key || action?.label || step.action_type]),
	});
}

export function stepParams(step) {
	try {
		return JSON.parse(step.params || "{}");
	} catch {
		return {};
	}
}
