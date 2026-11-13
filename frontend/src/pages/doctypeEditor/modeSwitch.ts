// The question the Design | Customize switch asks when edits are pending: Save first, Discard or Cancel.
import type { RouteLocationNormalized } from "vue-router";

export type ModeSwitchAnswer = "save" | "discard" | null;

type Route = Pick<RouteLocationNormalized, "params" | "query">;

/** The editor's route update: another DocType leaves, a `?mode=` change switches, the rest stays. */
export function guardRouteUpdate(
	to: Route,
	from: Route,
	confirm: { leave: () => Promise<boolean>; switchMode: () => Promise<boolean> },
): true | Promise<boolean> {
	if (to.params.name !== from.params.name) return confirm.leave();
	return to.query.mode === from.query.mode || confirm.switchMode();
}

/** True when the editor may switch modes: nothing pending, the save went through, or the edits were let go. */
export async function confirmModeSwitch(prompt: {
	dirty: boolean;
	ask: () => Promise<ModeSwitchAnswer>;
	save: () => Promise<boolean>;
}): Promise<boolean> {
	if (!prompt.dirty) return true;
	const answer = await prompt.ask();
	if (answer === "save") return prompt.save();
	return answer === "discard";
}
