import type { ReactNode } from 'react';
import { useId } from 'react';

export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; hint?: string }) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex cursor-pointer items-center justify-between gap-3 py-1" title={hint}>
      <span className="text-sm text-ink">{label}</span>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${checked ? 'bg-accent' : 'bg-line-strong'}`}
      >
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-bg transition-transform ${checked ? 'translate-x-4' : 'translate-x-0.5'}`} />
      </button>
    </label>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label, size = 'sm' }: {
  value: T; options: { value: T; label: ReactNode; title?: string }[]; onChange: (v: T) => void; label: string; size?: 'sm' | 'xs';
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-full bg-soft p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={`rounded-full font-medium transition-colors ${size === 'xs' ? 'px-2.5 py-0.5 text-xs' : 'px-3.5 py-1 text-sm'} ${value === o.value ? 'bg-accent text-accent-ink' : 'text-faint hover:text-ink'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Slider({ label, value, min, max, step, onChange, format, hint, right }: {
  label: ReactNode; value: number; min: number; max: number; step: number; onChange: (v: number) => void;
  format: (v: number) => ReactNode; hint?: ReactNode; right?: ReactNode;
}) {
  const id = useId();
  return (
    <div className="py-1">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-sm text-ink">{label}</label>
        <span className="num text-sm font-semibold text-ink">{format(value)}{right}</span>
      </div>
      <input id={id} type="range" className="w-full" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))} aria-valuetext={String(format(value))} />
      {hint && <div className="mt-0.5 text-xs text-faint">{hint}</div>}
    </div>
  );
}

export function NumberField({ label, value, onChange, prefix, suffix, min, max, step = 1, width = 'w-28' }: {
  label: string; value: number; onChange: (v: number) => void; prefix?: string; suffix?: string; min?: number; max?: number; step?: number; width?: string;
}) {
  const id = useId();
  return (
    <div className="flex items-center justify-between gap-3 py-1">
      <label htmlFor={id} className="text-sm text-ink">{label}</label>
      <div className={`flex items-center rounded-full border border-line bg-surface px-3 focus-within:border-ink ${width}`}>
        {prefix && <span className="text-sm text-faint">{prefix}</span>}
        <input id={id} type="number" inputMode="numeric" className="num w-full bg-transparent px-1 py-1.5 text-right text-sm text-ink focus:outline-none"
          value={value} min={min} max={max} step={step} onChange={(e) => { const v = Number(e.target.value); if (Number.isFinite(v)) onChange(v); }} />
        {suffix && <span className="text-sm text-faint">{suffix}</span>}
      </div>
    </div>
  );
}

export function Chip({ active, onClick, children, title }: { active: boolean; onClick: () => void; children: ReactNode; title?: string }) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick} title={title}
      className={`chip transition-colors ${active ? 'border-ink bg-soft text-ink' : 'text-faint hover:text-ink hover:border-line-strong'}`}>
      {children}
    </button>
  );
}
