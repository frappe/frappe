import { tags as t } from "@lezer/highlight"
import { createTheme } from "thememirror"

export const tomorrowNight = createTheme({
	variant: "dark",
	settings: {
		background: "var(--surface-base)",
		foreground: "#C5C8C6",
		caret: "#AEAFAD",
		selection: "#373B41",
		gutterBackground: "var(--surface-base)",
		gutterForeground: "#C5C8C680",
		lineHighlight: "#282A2E",
	},
	styles: [
		{ tag: t.comment, color: "#969896" },
		{ tag: [t.variableName, t.self, t.propertyName, t.attributeName, t.regexp], color: "#CC6666" },
		{ tag: [t.number, t.bool, t.null], color: "#DE935F" },
		{ tag: [t.className, t.typeName, t.definition(t.typeName)], color: "#F0C674" },
		{ tag: [t.string, t.special(t.brace)], color: "#B5BD68" },
		{ tag: t.operator, color: "#8ABEB7" },
		{ tag: [t.definition(t.propertyName), t.function(t.variableName)], color: "#81A2BE" },
		{ tag: t.keyword, color: "#B294BB" },
		{ tag: t.derefOperator, color: "#C5C8C6" },
	],
})
