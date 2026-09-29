// @vitest-environment node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { afterEach, describe, expect, it } from "vitest";
import { sourceBase } from "../diagram.mjs";

const repos: string[] = [];

function repo(remote?: string) {
	const root = fs.mkdtempSync(path.join(os.tmpdir(), "desk-source-"));
	repos.push(root);
	const git = (...args: string[]) => execFileSync("git", args, { cwd: root, encoding: "utf8" }).trim();
	git("init", "-q");
	git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "--allow-empty", "-m", "start");
	if (remote) git("remote", "add", "origin", remote);
	return { root, head: git("rev-parse", "HEAD") };
}

afterEach(() => repos.splice(0).forEach((root) => fs.rmSync(root, { recursive: true, force: true })));

describe("sourceBase", () => {
	it("links to the commit on GitHub, from an SSH address", () => {
		const { root, head } = repo("git@github.com:team/app.git");
		expect(sourceBase(root)).toBe(`https://github.com/team/app/blob/${head}/`);
	});

	it("never puts a token from the remote address in the link", () => {
		const { root, head } = repo("https://user:secret-token@github.com/team/app.git");
		expect(sourceBase(root)).toBe(`https://github.com/team/app/blob/${head}/`);
	});

	it("gives no base for a forge whose link format it does not know", () => {
		expect(sourceBase(repo("https://gitlab.example.com/team/app.git").root)).toBeNull();
	});

	it("gives no base for a remote that is a local path", () => {
		expect(sourceBase(repo("/srv/git/app.git").root)).toBeNull();
	});

	it("gives no base when the checkout has no remote", () => {
		expect(sourceBase(repo().root)).toBeNull();
	});
});
