import fs from "fs"
import path from "path"
import { CompletedConfig, createFormatter, createParser, createProgram, SchemaGenerator } from "ts-json-schema-generator"
import { SVGElementParser, VueComponentParser, RouteLocationParser } from "./customParser.js"

function tsToJSON(typesFolder: string, destFolder: string, tsconfig = "", isFrappeUI = false) {
	// Get project root (where package.json is)
	const root = process.cwd()
	const inputDirPath = path.resolve(root, typesFolder)
	const outputDirPath = path.resolve(root, destFolder)
	const tsconfigPath = tsconfig ? path.resolve(root, tsconfig) : ""

	const typeFiles = findTypeFiles(inputDirPath, isFrappeUI)

	let config = {
		skipTypeCheck: true,
		expose: "none", // only include explicitly requested types
		topRef: true, // add top-level $ref
		jsDoc: "extended", // include JSDoc annotations
		additionalProperties: false,
	} as CompletedConfig

	if (tsconfigPath) {
		config["tsconfig"] = tsconfig ? path.resolve(root, tsconfig) : ""
	}

	for (const { filePath, componentName } of typeFiles) {
		config["path"] = filePath
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

function findTypeFiles(dir: string, isFrappeUI: boolean): Array<{ filePath: string; componentName: string }> {
	const typeFiles: Array<{ filePath: string; componentName: string }> = []

	if (isFrappeUI) {
		// frappe-ui structure: types.ts files in subdirectories of components
		function scanDirectory(currentDir: string) {
			const items = fs.readdirSync(currentDir, { withFileTypes: true })
			for (const item of items) {
				const fullPath = path.join(currentDir, item.name)
				if (item.isDirectory()) {
					scanDirectory(fullPath)
				} else if (item.isFile() && item.name === "types.ts") {
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

function generateSchema(config: CompletedConfig, componentName: string, outputDirPath: string) {
	const program = createProgram(config)
	const parser = createParser(program, config, (prs) => {
		prs.addNodeParser(new SVGElementParser())
		prs.addNodeParser(new VueComponentParser())
		prs.addNodeParser(new RouteLocationParser())
	})
	const formatter = createFormatter(config)

	const generator = new SchemaGenerator(program, parser, formatter, config)
	const schema = generator.createSchema(config.type)
	if (!fs.existsSync(outputDirPath)) {
		fs.mkdirSync(outputDirPath, { recursive: true })
	}
	const outputFilePath = path.resolve(outputDirPath, `${componentName}.json`)
	const schemaString = JSON.stringify(schema, null, 2)
	fs.writeFileSync(outputFilePath, schemaString)
}

export default tsToJSON
