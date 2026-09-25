// Sequencing that stays synchronous until a step returns a promise, so a replay of
// synchronous handlers commits in the same task that started it.

export type MaybePromise<T = void> = T | Promise<T>;

function isThenable(value: unknown): value is PromiseLike<unknown> {
  return typeof (value as PromiseLike<unknown> | null)?.then === "function";
}

/** Runs `next` after `value`: at once for a plain value, on resolve for a promise. */
export function andThen<T>(value: unknown, next: () => MaybePromise<T>): MaybePromise<T> {
  return isThenable(value) ? Promise.resolve(value).then(next) : next();
}

/** Runs `work`, then `after` once it is done, whether it returned, threw or rejected. */
export function settle<T>(work: () => T, after: () => void): T {
  let result: T;
  try {
    result = work();
  } catch (error) {
    after();
    throw error;
  }
  if (!isThenable(result)) {
    after();
    return result;
  }
  return Promise.resolve(result).finally(after) as T;
}

/** Runs `work` and hands a throw or a rejection to `recover`. */
export function guard(work: () => unknown, recover: (error: unknown) => void): MaybePromise {
  try {
    const result = work();
    if (isThenable(result)) return Promise.resolve(result).then(() => {}, recover);
  } catch (error) {
    recover(error);
  }
}

/** Runs `step` over `items` in order; the rest wait only once a step returns a promise. */
export function inOrder<T>(items: T[], step: (item: T) => unknown, from = 0): MaybePromise {
  for (let index = from; index < items.length; index++) {
    const result = step(items[index]);
    if (isThenable(result))
      return Promise.resolve(result).then(() => inOrder(items, step, index + 1));
  }
}
