type FontSize =
	| "text-2xs"
	| "text-xs"
	| "text-sm"
	| "text-base"
	| "text-lg"
	| "text-xl"
	| "text-2xl"
	| "text-3xl"
	| "text-p-2xs"
	| "text-p-xs"
	| "text-p-sm"
	| "text-p-base"
	| "text-p-lg"
	| "text-p-xl"
	| "text-p-2xl"
	| "text-p-3xl"
type FontWeight = "font-thin" | "font-extralight" | "font-light" | "font-normal" | "font-medium" | "font-semibold" | "font-bold" | "font-extrabold" | "font-black"
type LineHeight =
	"leading-3"
	| "leading-4"
	| "leading-5"
	| "leading-6"
	| "leading-7"
	| "leading-8"
	| "leading-9"
	| "leading-10"
	| "leading-none"
	| "leading-tight"
	| "leading-snug"
	| "leading-normal"
	| "leading-relaxed"
	| "leading-loose"
type TextColor =
	"text-ink-gray-1"
	| "text-ink-gray-2"
	| "text-ink-gray-3"
	| "text-ink-gray-4"
	| "text-ink-gray-5"
	| "text-ink-gray-6"
	| "text-ink-gray-7"
	| "text-ink-gray-8"
	| "text-ink-gray-9"

export interface TextBlockProps {
	tag?: string
	fontSize?: FontSize
	fontWeight?: FontWeight
	lineHeight?: LineHeight
	textColor?: TextColor
	text?: string
}