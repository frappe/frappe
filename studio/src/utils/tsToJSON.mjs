import fs from "fs"
import path from "path"
import { createGenerator } from "ts-json-schema-generator"

function tsToJSON(typesFolder, destFolder, tsconfig = "") {
	// Get project root (where package.json is)
	const root = process.cwd()

	const inputDirPath = path.resolve(root, typesFolder)
	const outputDirPath = path.resolve(root, destFolder)

	const tsconfigPath = tsconfig ? path.resolve(root, tsconfig) : ""

	// Get a list of all the component type files
	const componentFiles = fs.readdirSync(inputDirPath).filter((file) => file.endsWith(".ts"))

	let config = { type: "*", skipTypeCheck: true }
	if (tsconfigPath) {
		config["tsconfig"] = tsconfigPath
	}

	// Generate a schema for each component type file
	for (const file of componentFiles) {
		const generator = createGenerator({
			path: path.join(inputDirPath, file),
			...config,
		})

		const schema = generator.createSchema()
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
