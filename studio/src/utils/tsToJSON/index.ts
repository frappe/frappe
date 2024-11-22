import fs from "fs"
import path from "path"
import { CompletedConfig, createFormatter, createParser, createProgram, SchemaGenerator } from "ts-json-schema-generator"
import { SVGElementParser } from "./customParser.js"

function tsToJSON(typesFolder: string, destFolder: string, tsconfig = "") {
	// Get project root (where package.json is)
	const root = process.cwd()

	const inputDirPath = path.resolve(root, typesFolder)
	const outputDirPath = path.resolve(root, destFolder)
	const tsconfigPath = tsconfig ? path.resolve(root, tsconfig) : ""

	// Get a list of all the component type files
	const componentFiles = fs.readdirSync(inputDirPath).filter((file) => file.endsWith(".ts"))

	let config = {
		type: "*", // Generate schema for all types
		skipTypeCheck: true,
		expose: "export", // only include exported types
		topRef: true, // add top-level $ref
		jsDoc: "extended", // include JSDoc annotations
		additionalProperties: false,
	} as CompletedConfig

	if (tsconfigPath) {
		config["tsconfig"] = tsconfigPath
	}

	// Generate a schema for each component type file
	for (const file of componentFiles) {
		config["path"] = path.join(inputDirPath, file)

		const program = createProgram(config)
		const parser = createParser(program, config, (prs) => {
			prs.addNodeParser(new SVGElementParser())
		})
		const formatter = createFormatter(config)

		const generator = new SchemaGenerator(program, parser, formatter, config)
		const schema = generator.createSchema(config.type)
		if (!fs.existsSync(outputDirPath)) {
			fs.mkdirSync(outputDirPath, { recursive: true })
		}

		const outputFilePath = path.resolve(outputDirPath, `${file.replace(".ts", "")}.json`)

		const schemaString = JSON.stringify(schema, null, 2)
		fs.writeFile(outputFilePath, schemaString, (err) => {
			if (err) throw err
			console.log(`Generated types for ${file} saved to ${outputFilePath}`)
		})
	}
}

export default tsToJSON
