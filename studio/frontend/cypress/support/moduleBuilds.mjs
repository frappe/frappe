import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { build } from "vite"
import vue from "@vitejs/plugin-vue"
import frappeui from "frappe-ui/vite"
import databaseAppImports from "../../vite/databaseAppImports.js"
import sharedDependencyResolver from "../../vite/sharedDependencyResolver.js"
import studioRootAlias from "../../vite/studioRootAlias.js"
import { moduleFixtures } from "../fixtures/module-fixtures.mjs"

const frontend = fileURLToPath(new URL("../../", import.meta.url))

/** Serve actual production fixture bundles to the component-test browser. */
export function moduleFixtureServer() {
	const root = fs.mkdtempSync(path.join(os.tmpdir(), "studio-module-parity-"))
	const builds = new Map()
	return {
		name: "studio-module-fixture-server",
		configureServer(server) {
			server.httpServer?.once("close", () => fs.rmSync(root, { recursive: true, force: true }))
			server.middlewares.use(async (req, res, next) => {
				const url = new URL(req.url, "http://studio.test")
				const match = url.pathname.match(/^\/__studio_parity__\/([^/]+)\/(.*)$/)
				if (!match) return next()
				const fixture = moduleFixtures.find((item) => item.name === match[1])
				if (!fixture) {
					res.writeHead(404).end()
					return
				}
				if (!builds.has(fixture.name)) builds.set(fixture.name, buildFixture(fixture, root))
				const result = await builds.get(fixture.name)
				res.setHeader("Cache-Control", "no-store")
				if (match[2] === "report.json") {
					res.setHeader("Content-Type", "application/json")
					res.end(JSON.stringify(result))
					return
				}
				const file = path.resolve(result.output, decodeURIComponent(match[2]))
				if (
					!result.ok ||
					!file.startsWith(result.output + path.sep) ||
					!fs.existsSync(file) ||
					!fs.statSync(file).isFile()
				) {
					res.writeHead(404).end()
					return
				}
				res.setHeader("Content-Type", file.endsWith(".css") ? "text/css" : "text/javascript")
				fs.createReadStream(file).pipe(res)
			})
		},
	}
}

async function buildFixture(fixture, root) {
	const folder = path.join(root, fixture.name, "studio", "fixture")
	const output = path.join(root, fixture.name, "output")
	for (const [file, source] of Object.entries(fixture.files)) {
		const target = path.join(folder, file)
		fs.mkdirSync(path.dirname(target), { recursive: true })
		fs.writeFileSync(target, source)
	}
	try {
		await build({
			configFile: false,
			root: folder,
			publicDir: false,
			base: `/__studio_parity__/${fixture.name}/`,
			logLevel: "silent",
			plugins: [
				vue(),
				frappeui({ buildConfig: false, codeLanguages: false, lucideIcons: false }),
				databaseAppImports(folder),
				studioRootAlias(),
				sharedDependencyResolver(frontend),
			],
			resolve: { dedupe: ["vue", "vue-router", "pinia", "frappe-ui"] },
			css: { postcss: { plugins: [] } },
			build: {
				outDir: output,
				emptyOutDir: true,
				target: "es2015",
				rolldownOptions: {
					input: path.join(folder, "entry.js"),
					preserveEntrySignatures: "strict",
					output: {
						entryFileNames: "entry.js",
						chunkFileNames: "[name]-[hash].js",
						assetFileNames: "[name][extname]",
					},
				},
			},
		})
		return { ok: true, output, css: fs.readdirSync(output).filter((file) => file.endsWith(".css")) }
	} catch (error) {
		return { ok: false, output, error: String(error.message) }
	}
}
