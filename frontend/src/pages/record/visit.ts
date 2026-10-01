// One visit to a record: each load starts one. Ending it aborts its reads, and a reply or a save
// that outlives it lands nothing, so a slower load cannot write over a newer one.
export class Visit {
  private readonly reading = new AbortController();
  private reads = 0;
  private newestLanding: Promise<void> = Promise.resolve();
  private toggles: Promise<void> = Promise.resolve();
  private saveRequest: Promise<void> | null = null;

  /** False once the visit ended; a child part keeps it across its own awaits. */
  readonly current = (): boolean => !this.reading.signal.aborted;

  /** Aborts the visit's reads when it ends, so a read left behind does not feed the cache. */
  get signal(): AbortSignal {
    return this.reading.signal;
  }

  /** Ends this visit and starts the next one, which queues its toggles behind this one's. */
  next(): Visit {
    this.end();
    const next = new Visit();
    next.toggles = this.toggles;
    return next;
  }

  end(): void {
    this.reading.abort();
  }

  /** Lands only the newest of overlapping reads; a replaced read resolves once the newest has landed. */
  readNewest<T>(read: (signal: AbortSignal) => Promise<T>, land: (value: T) => void): Promise<void> {
    this.newestLanding = this.landIfNewest(++this.reads, read, land);
    return this.newestLanding;
  }

  /** Runs a toggle once the toggles queued before it, on this visit or an earlier one, are done. */
  inTurn(turn: () => Promise<void>): Promise<void> {
    this.toggles = this.toggles.then(turn, turn);
    return this.toggles;
  }

  /** One save request at a time; a save asked while one is in flight joins it. */
  save(send: () => Promise<void>): Promise<void> {
    this.saveRequest ??= send().finally(() => {
      this.saveRequest = null;
    });
    return this.saveRequest;
  }

  private async landIfNewest<T>(
    mine: number,
    read: (signal: AbortSignal) => Promise<T>,
    land: (value: T) => void
  ): Promise<void> {
    let value: T;
    try {
      value = await read(this.signal);
    } catch (error) {
      if (!this.current()) return;
      throw error;
    }
    if (!this.current()) return;
    if (mine !== this.reads) return this.newestLanding;
    land(value);
  }
}
