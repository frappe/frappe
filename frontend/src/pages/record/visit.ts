// One visit to a record: each load starts one. A reply, a toggle or a save that outlives its
// visit does nothing, so the slower of two loads cannot write over the newer one.
export class Visit {
  private ended = false;
  private docinfoReads = 0;
  private docinfoLanding: Promise<void> = Promise.resolve();
  private toggles: Promise<void> = Promise.resolve();
  private saveRequest: Promise<void> | null = null;

  /** False once the next visit started; a child part keeps it across its own awaits. */
  readonly current = (): boolean => !this.ended;

  /** Ends this visit and starts the next one. */
  next(): Visit {
    this.ended = true;
    return new Visit();
  }

  /** Lands only the newest of overlapping reads; a replaced read resolves once the newest has landed. */
  readNewest<T>(read: () => Promise<T>, land: (value: T) => void): Promise<void> {
    const mine = ++this.docinfoReads;
    this.docinfoLanding = read().then((value) => {
      if (this.ended) return;
      if (mine !== this.docinfoReads) return this.docinfoLanding;
      land(value);
    });
    return this.docinfoLanding;
  }

  /** Runs a toggle after the ones queued before it; a turn that outlived its visit does nothing. */
  inTurn(turn: () => Promise<void>): Promise<void> {
    this.toggles = this.toggles.then(() => (this.ended ? undefined : turn()));
    return this.toggles;
  }

  /** One save request at a time; a save asked while one is in flight joins it. */
  save(send: () => Promise<void>): Promise<void> {
    this.saveRequest ??= send().finally(() => {
      this.saveRequest = null;
    });
    return this.saveRequest;
  }
}
