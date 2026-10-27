// The palette's last row, which hands the typed text to Flow as a new chat. Flow's launcher
// sets the flag and listens for the event; the palette imports nothing from Flow.
import { __ } from "@/i18n";
import type { PaletteRow } from "./palette";

/** "Ask Flow: <text>", while something is typed and Flow's launcher says it is ready. */
export function askFlow(query: string): PaletteRow[] {
	const text = query.trim();
	if (!text || document.documentElement.dataset.flow !== "ready") return [];
	return [
		{
			id: "ask-flow",
			lead: __("Ask Flow:"),
			label: text,
			icon: "lucide-sparkles",
			hint: __("New chat in Flow"),
			run: () => window.dispatchEvent(new CustomEvent("flow:ask", { detail: { text } })),
		},
	];
}
