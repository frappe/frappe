import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"
import { createGenerator } from "ts-json-schema-generator"

const dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.join(dirname, "..", "..")

const componentsDir = "../node_modules/frappe-ui/src/components/types"
const tsconfigPath = "../node_modules/frappe-ui/tsconfig.json"

// Get a list of all the component type files
const componentFiles = fs.readdirSync(path.join(root, componentsDir)).filter((file) => file.endsWith(".ts"))

// Generate a schema for each component type file
for (const file of componentFiles) {
	const generator = createGenerator({
		path: path.join(componentsDir, file),
		type: "*",
		tsconfig: tsconfigPath,
		skipTypeCheck: true,
	})

	const schema = generator.createSchema()
	const outputDirPath = path.join(root, "src", "frappeui_types")

	if (!fs.existsSync(outputDirPath)) {
		fs.mkdirSync(outputDirPath)
	}

	const outputFilePath = path.resolve(outputDirPath, `${file.replace(".ts", "")}.json`)

	const schemaString = JSON.stringify(schema, null, 2)
	fs.writeFile(outputFilePath, schemaString, (err) => {
		if (err) throw err
		console.log(`Generated types for ${file} saved to ${outputFilePath}`)
	})
}
