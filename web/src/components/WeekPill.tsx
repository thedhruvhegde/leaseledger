import { useId } from 'react';

/** Signature input: describe your week in one soft-gray mono pill; the arrow (or Enter) reads it. */
export function WeekPill({ value, onChange, onSubmit, pending = false, placeholder, label = 'Describe your week', id, size = 'md' }: {
  value: string; onChange: (v: string) => void; onSubmit: () => void; pending?: boolean; placeholder: string; label?: string; id?: string; size?: 'md' | 'lg';
}) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <div className="relative">
      <label htmlFor={fid} className="sr-only">{label}</label>
      <textarea
        id={fid}
        rows={1}
        maxLength={2000}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (value.trim()) onSubmit(); } }}
        className={`week-pill mono block w-full border border-transparent bg-soft py-4 pl-6 pr-16 text-ink placeholder:text-faint focus:border-line-strong focus:bg-surface focus:outline-none ${size === 'lg' ? 'text-base' : 'text-[0.9375rem]'}`}
      />
      <button type="button" onClick={onSubmit} disabled={pending || !value.trim()} aria-label={pending ? 'Reading your week' : 'Read my week'}
        className="absolute bottom-2 right-2 flex h-10 w-10 items-center justify-center rounded-full bg-accent text-accent-ink transition-[transform,opacity] hover:bg-ink/80 active:scale-95 disabled:opacity-35">
        {pending ? <span className="h-3 w-3 animate-pulse2 rounded-full bg-current" /> : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M5 12h14M13 6l6 6-6 6" /></svg>
        )}
      </button>
    </div>
  );
}
