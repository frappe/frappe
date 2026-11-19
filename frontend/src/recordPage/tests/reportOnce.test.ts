import { expect, it, vi } from "vitest";
import { reportOnce } from "../reportOnce";

it("reports one error object once, and hands a later caller the first result", () => {
  const report = vi.fn(() => Promise.resolve());
  const once = reportOnce(report);
  const error = new Error("refused");

  const first = once(error);

  expect(once(error)).toBe(first);
  expect(report).toHaveBeenCalledTimes(1);
});

it("reports a different error, and a thrown primitive each time", () => {
  const report = vi.fn();
  const once = reportOnce(report);

  once(new Error("one"));
  once(new Error("two"));
  once("refused");
  once("refused");

  expect(report).toHaveBeenCalledTimes(4);
});

it("counts the same error once across two reporters", () => {
  const first = vi.fn();
  const second = vi.fn();
  const error = new Error("refused");

  reportOnce(first)(error);
  reportOnce(second)(error);

  expect(second).not.toHaveBeenCalled();
});
