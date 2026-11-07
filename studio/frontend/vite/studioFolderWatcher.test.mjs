import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import test from "node:test"
import studioFolderWatcher from "./studioFolderWatcher.js"

test("page scripts and router files accept HMR with either extension", () => {
	const appsDir = fs.mkdtempSync(path.join(os.tmpdir(), "studio-script-hmr-"))
	try {
		const appFolder = path.join(appsDir, "example", "studio", "notes")
		const pageFolder = path.join(appFolder, "studio_page", "board")
		fs.mkdirSync(pageFolder, { recursive: true })
		fs.writeFileSync(path.join(appFolder, "notes.json"), "{}")
		fs.writeFileSync(path.join(pageFolder, "board.json"), JSON.stringify({ page_name: "board-page" }))
		const plugin = studioFolderWatcher(appsDir)
		for (const extension of ["ts", "js"]) {
			const page = path.join(pageFolder, `board.${extension}`)
			for (const id of [page, `/@fs${page}?v=1`]) {
				const result = plugin.transform("export default function setup() {}", id)
				assert.match(result.code, /import\.meta\.hot\.accept/)
				assert.match(result.code, /__STUDIO_HMR_applyPageScript\("board-page", mod\)/)
			}
			const router = plugin.transform("export default {}", path.join(appFolder, `router.${extension}`))
			assert.match(router.code, /import\.meta\.hot\.accept/)
			assert.match(router.code, /window\.location\.reload/)
			assert.equal(
				plugin.transform("export const one = 1", path.join(appFolder, `helpers.${extension}`)),
				undefined,
			)
		}
	} finally {
		fs.rmSync(appsDir, { recursive: true, force: true })
	}
})
