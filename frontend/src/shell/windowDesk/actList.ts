// What `window.desk.acts.list` and `options` answer: the acts that can run now, and an act's choices for a query.
import { acts, ActDenied, type ActResult, type AvailableAct } from "@/acts/dispatcher";
import type { ActSchema } from "@/acts/schema/checkValue";
import { callResult } from "@/acts/callResult";
import { readDialogs } from "../dialogs/readableDialogs";

export interface ListedAct {
	name: string;
	label: string;
	description: string;
	/** The JSON Schema of the value `run` takes; `null` when the act takes none. */
	input: ActSchema | null;
	output?: ActSchema;
	asks: string[];
	surface: string;
	key?: string;
	has_options: boolean;
}

export async function listActs(): Promise<ListedAct[]> {
	return (await acts.described()).map(listed);
}

export function optionsOf(name: string, query: string): Promise<ActResult> {
	return callResult(choices(name, query), name, readDialogs);
}

function listed(act: AvailableAct): ListedAct {
	const label = act.label ?? act.name;
	return {
		name: act.name,
		label,
		description: act.description ?? label,
		input: act.input ?? null,
		...(act.output && { output: act.output }),
		asks: act.asks ?? [],
		surface: act.name.slice(0, act.name.indexOf(".")),
		...(act.key && { key: act.key }),
		has_options: !!act.argument,
	};
}

async function choices(name: string, query: string) {
	await acts.ready(name);
	const act = acts.find(name);
	if (!act) throw new ActDenied(name, "missing");
	if (!act.argument) throw new Error(`${name} has no options`);
	const options = await act.argument.options(query);
	return options.map(({ value, label, description, disabled }) => ({ value, label, description, disabled }));
}
