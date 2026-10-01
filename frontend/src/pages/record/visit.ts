// One visit to a record: each load starts one. A reply or a save that outlives its visit lands
// nothing, so a slower load cannot write over a newer one. Toggles queue across visits.
export class Visit {
  private ended = false;
  private reads = 0;
  private newestLanding: Promise<void> = Promise.resolve();
  private toggles: Promise<void> = Promise.resolve();
  private saveRequest: Promise<void> | null = null;

  /** False once the next visit started; a child part keeps it across its own awaits. */
  readonly current = (): boolean => !this.ended;

  /** Ends this visit and starts the next one, which queues its toggles behind this one's. */
  next(): Visit {
    this.ended = true;
    const next = new Visit();
    next.toggles = this.toggles;
    return next;
  }

  /** Lands only the newest of overlapping reads; a replaced read resolves once the newest has landed. */
  readNewest<T>(read: () => Promise<T>, land: (value: T) => void): Promise<void> {
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
    read: () => Promise<T>,
    land: (value: T) => void
  ): Promise<void> {
    const value = await read();
    if (this.ended) return;
    if (mine !== this.reads) return this.newestLanding;
    land(value);
  }
}
