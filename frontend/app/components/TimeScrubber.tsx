interface TimeScrubberProps {
  timeS: number[];
  index: number;
  onChange: (index: number) => void;
}

/**
 * Selects an index into the already-loaded Scenario A timeseries.
 * No simulation run, no API call, no interpolation -- moving this
 * slider only changes which already-returned sample is displayed.
 */
export function TimeScrubber({ timeS, index, onChange }: TimeScrubberProps) {
  return (
    <section className="flex flex-col gap-2 border border-hairline bg-surface px-4 py-3">
      <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
        TIME
      </span>
      <input
        type="range"
        min={0}
        max={timeS.length - 1}
        step={1}
        value={index}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1 w-full cursor-pointer appearance-none rounded-none bg-hairline accent-accent"
      />
      <span className="font-mono text-[12px] tabular-nums text-secondary">
        t = {timeS[index].toFixed(4)} s
      </span>
    </section>
  );
}
