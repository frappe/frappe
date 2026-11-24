// The classes that a block can take from its props, so no source file names them.
export default [
	// TextBlock sets its size via a dynamic `:class="[fontSize]"` binding
	// Sync with `fontSize` union in src/types/studio_components/TextBlock.ts.
	"text-2xs",
	"text-xs",
	"text-sm",
	"text-base",
	"text-md",
	"text-lg",
	"text-xl",
	"text-2xl",
	"text-3xl",
	"text-4xl",
	"text-5xl",
	"text-6xl",
	"text-7xl",
	"text-8xl",
	"text-9xl",
	"text-10xl",
	"text-11xl",
	"text-12xl",
	"text-p-xs",
	"text-p-sm",
	"text-p-base",
	"text-p-md",
	"text-p-lg",
	"text-p-xl",
	"text-p-2xl",
	"text-p-3xl",
	"text-p-4xl",
	// app builds replace this with only the icons their pages use (src/scripts/build.js)
	{ pattern: /^lucide-/ },
]
