import { build } from "vite"
import { readFileSync, readdirSync } from "node:fs"
import { gzipSync } from "node:zlib"
const out = process.argv[2]
await build({ root: process.cwd(), logLevel: "error", build: { outDir: out, emptyOutDir: true, manifest: true } })
const m = JSON.parse(readFileSync(out + "/.vite/manifest.json", "utf8"))
const seen = new Set()
const walk = k => { const c = m[k]; if (!c || seen.has(c.file)) return; seen.add(c.file); (c.imports ?? []).forEach(walk) }
walk("index.html"); walk("src/pages/Record.vue"); walk("src/pages/NewRecord.vue")
const rows = [...seen].map(f => [f.replace(/-[\w-]{8}\.js$/, ""), gzipSync(readFileSync(out + "/" + f)).length])
console.log(JSON.stringify(Object.fromEntries(rows)))
