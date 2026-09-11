// The reader's form tab, per doctype and per user, in the browser.
import { beforeEach, describe, expect, it } from "vitest";
import { formTabMemory } from "../formTabMemory";

beforeEach(() => localStorage.clear());

describe("formTabMemory", () => {
  it("answers nothing until the reader chooses", () => {
    expect(formTabMemory("alice", "CRM Deal").recall()).toBe("");
  });

  it("remembers the last choice per doctype", () => {
    const deal = formTabMemory("alice", "CRM Deal");
    const lead = formTabMemory("alice", "CRM Lead");
    deal.remember("products");
    lead.remember("details");
    deal.remember("activity");
    expect(deal.recall()).toBe("activity");
    expect(lead.recall()).toBe("details");
  });

  it("keeps one reader's choice from another's", () => {
    formTabMemory("alice", "CRM Deal").remember("products");
    expect(formTabMemory("bob", "CRM Deal").recall()).toBe("");
  });

  it("survives a broken store", () => {
    localStorage.setItem("frappe:desk:formTab", "not json");
    const memory = formTabMemory("alice", "CRM Deal");
    expect(memory.recall()).toBe("");
    memory.remember("products");
    expect(memory.recall()).toBe("products");
  });
});
