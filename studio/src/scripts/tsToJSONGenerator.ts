import tsToJSON from "../utils/tsToJSON"
import fs from "fs"
import path from "path"

const configMap: Record<string, any> = {
	frappeui: {
		srcFolders: [
			"../node_modules/frappe-ui/src/components",
			"../node_modules/frappe-ui/frappe",
		],
		destFolder: "src/json_types/frappeui",
		tsconfigPath: "../node_modules/frappe-ui/tsconfig.base.json",
		// Filter and Link now ship from @framework/ui (see the frameworkui config),
		// so skip the frappe-ui/frappe versions to avoid duplicate json_types exports.
		skipFolders: ["drive", "Filter", "Link"],
		// component-per-folder layout: scan for `types.ts`, key by folder name
		folderScan: true,
	},
	// @framework/ui (apps/frappe/ui). Extracted per-component (a folder can hold
	// several components), keyed off the `.vue` files: each component that exports
	// `<Component>Props` (and optionally `<Component>Slots`) in its folder's `types.ts`
	// gets one `<Component>.json`.
	frameworkui: {
		srcFolders: ["../../frappe/ui/src/components"],
		destFolder: "src/json_types/frameworkui",
		tsconfigPath: "../node_modules/frappe-ui/tsconfig.base.json",
		skipFolders: ["stories", "tests"],
		// ComposerEditor is the private editing core shared by Email/CommentComposer —
		// it exports Props (for the composers to extend) but is not a studio block.
		skipComponents: ["ComposerEditor"],
		perComponent: true,
	},
	studio: {
		srcFolders: ["src/types/studio_components"],
		destFolder: "src/json_types/studio",
		tsconfigPath: "tsconfig.json",
	},
}

const moduleName = process.argv[2]
if (!moduleName || !configMap[moduleName]) {
	console.error(
		`Invalid or missing moduleName. Please specify one of the following modules:\n- ${Object.keys(
			configMap,
		).join("\n- ")}`,
	)
	process.exit(1)
}

/* 1. Generate JSON types */
const { srcFolders, destFolder, tsconfigPath, skipFolders, folderScan, perComponent, skipComponents } =
	configMap[moduleName]

// Generate in place (no upfront wipe). Aggregate which components exist in source
// (`expected`) across all source folders, so a component whose schema fails to
// generate this run keeps its previously-committed JSON instead of vanishing — a
// frappe-ui bump that breaks extraction degrades to a stale schema, not a missing
// one. Only truly gone components (renamed/removed upstream) are pruned below.
const expected = new Set<string>()
srcFolders.forEach((srcFolder: string) => {
	const result = tsToJSON(
		srcFolder,
		destFolder,
		skipFolders,
		tsconfigPath,
		Boolean(folderScan),
		Boolean(perComponent),
		skipComponents,
	)
	result.expected.forEach((name) => expected.add(name))
})

// Prune stale JSON: drop only files whose component no longer exists in source, so
// renamed/removed components don't linger in the index. Failed-but-still-present
// components are in `expected`, so their old JSON is kept.
if (fs.existsSync(destFolder)) {
	for (const file of fs.readdirSync(destFolder)) {
		if (file.endsWith(".json") && !expected.has(path.parse(file).name)) {
			fs.rmSync(path.join(destFolder, file))
			console.log(`Pruned ${file} (no matching component in source)`)
		}
	}
}

/* 2. Update index file */
const indexFilePath = "src/json_types/index.ts"
const root = process.cwd()
const inputDirPath = path.resolve(root, destFolder)
const files = fs.readdirSync(inputDirPath)

const exports = files
	.filter((file) => file.endsWith(".json"))
	.map((file) => {
		const fileName = path.parse(file).name
		return `export { default as ${fileName} } from "./${moduleName}/${fileName}.json"`
	})

let existingContent = ""
if (fs.existsSync(indexFilePath)) {
	existingContent = fs.readFileSync(indexFilePath, "utf-8")
}

// find or create the export block for the module
const sectionStartMarker = `// ${moduleName} components`
const sectionEndMarker = `// end of ${moduleName} components`
const sectionRegex = new RegExp(
	`${sectionStartMarker}[\\s\\S]*?${sectionEndMarker}`,
	"g"
)
let updatedContent
if (sectionRegex.test(existingContent)) {
	// replace the existing section
	updatedContent = existingContent.replace(
		sectionRegex,
		`${sectionStartMarker}\n${exports.join("\n")}\n${sectionEndMarker}`
	).trim() + "\n"
} else {
	// add a new section
	updatedContent = `${existingContent.trim()}\n\n${sectionStartMarker}\n${exports.join("\n")}\n${sectionEndMarker}`.trim() + "\n"
}

fs.writeFileSync(indexFilePath, updatedContent, "utf-8")
console.log(`Generated index.ts at ${indexFilePath}`)
