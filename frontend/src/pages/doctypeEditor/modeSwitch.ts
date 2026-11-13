// The question the Design | Customize switch asks when edits are pending: Save first, Discard or Cancel.
export type ModeSwitchAnswer = "save" | "discard" | null;

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
