// One visit to a record: stale reads, toggles and saves from an ended visit do nothing.
import { describe, expect, it, vi } from "vitest";
import { Visit } from "../visit";

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function flush() {
  for (let i = 0; i < 20; i++) await Promise.resolve();
}

describe("Visit.current", () => {
  it("is true for a new visit", () => {
    expect(new Visit().current()).toBe(true);
  });

  it("is false for the old visit after next, and true for the new one", () => {
    const old = new Visit();
    const fresh = old.next();
    expect(old.current()).toBe(false);
    expect(fresh.current()).toBe(true);
  });

  it("works when detached from the visit", () => {
    const visit = new Visit();
    const check = visit.current;
    expect(check()).toBe(true);
    visit.next();
    expect(check()).toBe(false);
  });
});

describe("Visit.readNewest", () => {
  it("lands only the newer of two overlapping reads", async () => {
    const visit = new Visit();
    const older = deferred<string>();
    const newer = deferred<string>();
    const land = vi.fn();
    const olderDone = visit.readNewest(() => older.promise, land);
    const newerDone = visit.readNewest(() => newer.promise, land);
    newer.resolve("new");
    await newerDone;
    older.resolve("old");
    await olderDone;
    expect(land).toHaveBeenCalledTimes(1);
    expect(land).toHaveBeenCalledWith("new");
  });

  it("resolves a replaced read only after the newest has landed", async () => {
    const visit = new Visit();
    const older = deferred<string>();
    const newer = deferred<string>();
    const log: string[] = [];
    const land = (value: string) => log.push(`land ${value}`);
    visit.readNewest(() => older.promise, land).then(() => log.push("older done"));
    visit.readNewest(() => newer.promise, land);
    older.resolve("old");
    await flush();
    expect(log).toEqual([]);
    newer.resolve("new");
    await flush();
    expect(log).toEqual(["land new", "older done"]);
  });

  it("lands nothing once the visit has ended", async () => {
    const visit = new Visit();
    const read = deferred<string>();
    const land = vi.fn();
    const done = visit.readNewest(() => read.promise, land);
    visit.next();
    read.resolve("late");
    await done;
    expect(land).not.toHaveBeenCalled();
  });

  it("rejects when the read rejects", async () => {
    const visit = new Visit();
    const land = vi.fn();
    await expect(visit.readNewest(() => Promise.reject(new Error("offline")), land)).rejects.toThrow(
      "offline",
    );
    expect(land).not.toHaveBeenCalled();
  });
});

describe("Visit.inTurn", () => {
  it("runs turns in the order queued, each after the one before finishes", async () => {
    const visit = new Visit();
    const first = deferred();
    const log: string[] = [];
    visit.inTurn(() => {
      log.push("first start");
      return first.promise.then(() => {
        log.push("first end");
      });
    });
    const second = visit.inTurn(async () => {
      log.push("second start");
    });
    await flush();
    expect(log).toEqual(["first start"]);
    first.resolve();
    await second;
    expect(log).toEqual(["first start", "first end", "second start"]);
  });

  it("skips a turn whose visit ended before its turn came", async () => {
    const visit = new Visit();
    const first = deferred();
    const turn = vi.fn(async () => {});
    visit.inTurn(() => first.promise);
    const skipped = visit.inTurn(turn);
    visit.next();
    first.resolve();
    await skipped;
    expect(turn).not.toHaveBeenCalled();
  });
});

describe("Visit.save", () => {
  it("joins a save asked while one is in flight", async () => {
    const visit = new Visit();
    const request = deferred();
    const send = vi.fn(() => request.promise);
    const log: string[] = [];
    visit.save(send).then(() => log.push("first"));
    visit.save(send).then(() => log.push("second"));
    expect(send).toHaveBeenCalledTimes(1);
    await flush();
    expect(log).toEqual([]);
    request.resolve();
    await flush();
    expect(log).toEqual(["first", "second"]);
  });

  it("sends again once the earlier save has settled", async () => {
    const visit = new Visit();
    const send = vi.fn(async () => {});
    await visit.save(send);
    await visit.save(send);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it("frees the slot after a save rejects", async () => {
    const visit = new Visit();
    const send = vi.fn().mockRejectedValueOnce(new Error("conflict")).mockResolvedValueOnce(undefined);
    await expect(visit.save(send)).rejects.toThrow("conflict");
    await visit.save(send);
    expect(send).toHaveBeenCalledTimes(2);
  });
});
