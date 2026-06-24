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
		skipFolders: ["drive"]
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
const { srcFolders, destFolder, tsconfigPath, skipFolders } = configMap[moduleName]
srcFolders.forEach((srcFolder: string) => {
	tsToJSON(srcFolder, destFolder, skipFolders, tsconfigPath, moduleName === "frappeui")
})

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
