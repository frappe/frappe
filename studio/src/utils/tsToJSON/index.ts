import fs from "fs"
import path from "path"
import { CompletedConfig, createFormatter, createParser, createProgram, SchemaGenerator } from "ts-json-schema-generator"
import { SVGElementParser, VueComponentParser, RouteLocationParser, HTMLElementParser, FunctionTypeParser, SlotsParser } from "./customParser.js"

interface TypeFile {
	filePath: string
	componentName: string
	// perComponent: whether the source also exports `<componentName>Slots`
	hasSlots?: boolean
}

function tsToJSON(
	srcFolder: string,
	destFolder: string,
	skipFolders: string[] | null = null,
	tsconfig = "",
	folderScan = false,
	perComponent = false,
) {
	// Get project root (where package.json is)
	const root = process.cwd()
	const inputDirPath = path.resolve(root, srcFolder)
	const outputDirPath = path.resolve(root, destFolder)
	const tsconfigPath = tsconfig ? path.resolve(root, tsconfig) : ""

	const typeFiles = perComponent
		? findComponentTypeFiles(inputDirPath, skipFolders)
		: findTypeFiles(inputDirPath, folderScan, skipFolders)

	let config = {
		skipTypeCheck: true,
		expose: "none", // only include explicitly requested types
		topRef: true, // add top-level $ref
		jsDoc: "none", // include JSDoc annotations
		additionalProperties: false,
	} as CompletedConfig

	if (tsconfigPath) {
		config["tsconfig"] = tsconfig ? path.resolve(root, tsconfig) : ""
	}

	for (const { filePath, componentName, hasSlots } of typeFiles) {
		config["path"] = filePath

		if (perComponent) {
			generateComponentSchema(config, componentName, Boolean(hasSlots), outputDirPath)
			continue
		}

		config["type"] = `${componentName}Props`
		try {
			generateSchema(config, componentName, outputDirPath)
			console.log(`Generated types for ${componentName} saved to ${componentName}.json`)
		} catch (error) {
			console.warn(`Failed to generate schema for ${componentName}Props, trying wildcard type`)
			config["type"] = "*"
			try {
				generateSchema(config, componentName, outputDirPath)
				console.log(`Generated types for ${componentName} saved to ${componentName}.json`)
			} catch (error) {
				console.error(`Failed to generate schema for ${componentName}:`, error)
			}
		}
	}
}

function findTypeFiles(dir: string, folderScan: boolean, skipFolders: string[] | null = null): TypeFile[] {
	const typeFiles: TypeFile[] = []

	if (folderScan) {
		// component-per-folder structure: types.ts files in subdirectories of components
		function scanDirectory(currentDir: string) {
			const items = fs.readdirSync(currentDir, { withFileTypes: true })
			for (const item of items) {
				const fullPath = path.join(currentDir, item.name)
				if (item.isDirectory()) {
					if (skipFolders && skipFolders.includes(item.name)) {
						continue
					}
					scanDirectory(fullPath)
				} else if (item.isFile() && item.name === "types.ts" && currentDir !== dir) {
					// skip a shared `types.ts` sitting directly in the components root
					// (it is not a component, e.g. @framework/ui's cross-component types)
					const componentName = path.basename(path.dirname(fullPath))
					typeFiles.push({ filePath: fullPath, componentName })
				}
			}
		}

		scanDirectory(dir)
	} else {
		// studio structure: individual .ts files in types folder
		const files = fs.readdirSync(dir).filter((file) => file.endsWith(".ts"))
		for (const file of files) {
			const filePath = path.join(dir, file)
			const componentName = path.basename(file, ".ts")
			typeFiles.push({ filePath, componentName })
		}
	}

	return typeFiles
}

// perComponent (@framework/ui): a folder can host several components (Notifications,
// ActivityTimeline, FileUpload, …), so drive extraction off the `.vue` files. A
// component is extracted when its sibling `types.ts` exports `<Component>Props`;
// `<Component>Slots` is picked up too when present. The Props/Slots type lives in the
// folder's `types.ts`, which is the schema-generation entry (`filePath`).
function findComponentTypeFiles(dir: string, skipFolders: string[] | null = null): TypeFile[] {
	const typeFiles: TypeFile[] = []

	function scanDirectory(currentDir: string) {
		const items = fs.readdirSync(currentDir, { withFileTypes: true })
		const vueFiles = items
			.filter((i) => i.isFile() && i.name.endsWith(".vue") && !i.name.endsWith(".story.vue"))
			.map((i) => path.basename(i.name, ".vue"))
		const typesPath = path.join(currentDir, "types.ts")
		const typesSource = fs.existsSync(typesPath) ? fs.readFileSync(typesPath, "utf-8") : ""

		for (const componentName of vueFiles) {
			if (!exportsType(typesSource, `${componentName}Props`)) continue
			typeFiles.push({
				filePath: typesPath,
				componentName,
				hasSlots: exportsType(typesSource, `${componentName}Slots`),
			})
		}

		for (const item of items) {
			if (item.isDirectory() && !(skipFolders && skipFolders.includes(item.name))) {
				scanDirectory(path.join(currentDir, item.name))
			}
		}
	}

	scanDirectory(dir)
	return typeFiles
}

function exportsType(source: string, typeName: string): boolean {
	return new RegExp(`export\\s+(?:interface|type)\\s+${typeName}\\b`).test(source)
}

function generateSchema(config: CompletedConfig, componentName: string, outputDirPath: string) {
	const schema = buildSchema(config)
	writeSchema(schema, componentName, outputDirPath)
}

// Emit one `<Component>.json` holding both `<Component>Props` and (when present)
// `<Component>Slots` under `definitions`, so the consumer can read either.
function generateComponentSchema(
	config: CompletedConfig,
	componentName: string,
	hasSlots: boolean,
	outputDirPath: string,
) {
	const definitions: Record<string, any> = {}
	try {
		config["type"] = `${componentName}Props`
		Object.assign(definitions, buildSchema(config).definitions)
	} catch (error) {
		console.error(`Failed to generate Props schema for ${componentName}: ${errorMessage(error)}`)
		return
	}

	if (hasSlots) {
		try {
			config["type"] = `${componentName}Slots`
			Object.assign(definitions, buildSchema(config).definitions)
		} catch (error) {
			// e.g. a generic `<Component>Slots<T>` can't be resolved by bare name — the
			// component keeps its Props schema and its slots are read from the template.
			console.warn(`Skipped Slots schema for ${componentName}: ${errorMessage(error)}`)
		}
	}

	writeSchema({ $schema: "http://json-schema.org/draft-07/schema#", definitions }, componentName, outputDirPath)
	console.log(`Generated types for ${componentName} saved to ${componentName}.json`)
}

function errorMessage(error: unknown): string {
	return error instanceof Error ? error.message : String(error)
}

function buildSchema(config: CompletedConfig) {
	const program = createProgram(config)
	const parser = createParser(program, config, (prs) => {
		prs.addNodeParser(new SVGElementParser())
		prs.addNodeParser(new VueComponentParser())
		prs.addNodeParser(new RouteLocationParser())
		prs.addNodeParser(new HTMLElementParser())
		prs.addNodeParser(new FunctionTypeParser())
		prs.addNodeParser(new SlotsParser())
	})
	const formatter = createFormatter(config)
	const generator = new SchemaGenerator(program, parser, formatter, config)
	return generator.createSchema(config.type)
}

function writeSchema(schema: unknown, componentName: string, outputDirPath: string) {
	if (!fs.existsSync(outputDirPath)) {
		fs.mkdirSync(outputDirPath, { recursive: true })
	}
	const outputFilePath = path.resolve(outputDirPath, `${componentName}.json`)
	fs.writeFileSync(outputFilePath, JSON.stringify(schema, null, 2))
}

export default tsToJSON
