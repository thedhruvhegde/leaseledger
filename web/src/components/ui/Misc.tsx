import type { ReactNode } from 'react';
import { IconAlert } from './Icons';

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function SectionTitle({ eyebrow, title, children, right }: { eyebrow?: string; title: ReactNode; children?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {eyebrow && <div className="label mb-1">{eyebrow}</div>}
        <h1 className="text-[1.625rem] font-semibold leading-tight text-ink">{title}</h1>
        {children && <p className="mt-1.5 max-w-3xl text-[15px] leading-relaxed text-charcoal">{children}</p>}
      </div>
      {right}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="text-base font-semibold text-ink">{title}</div>
      {children && <div className="max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="card flex items-start gap-3 border-bad/40 p-4">
      <IconAlert className="mt-0.5 text-bad" />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-ink">Something went wrong</div>
        <div className="mt-0.5 break-words text-xs text-muted">{msg}</div>
      </div>
      {retry && <button className="btn-outline" onClick={retry}>Retry</button>}
    </div>
  );
}

export function Stat({ value, unit, label, tone = 'text-ink', size = 'lg' }: { value: ReactNode; unit?: string; label?: ReactNode; tone?: string; size?: 'lg' | 'md' | 'sm' }) {
  const s = size === 'lg' ? 'text-3xl' : size === 'md' ? 'text-xl' : 'text-base';
  return (
    <div className="min-w-0">
      <div className={`mono font-medium ${s} ${tone}`}>
        {value}
        {unit && <span className="ml-0.5 text-[0.55em] font-medium text-faint">{unit}</span>}
      </div>
      {label && <div className="text-xs text-muted">{label}</div>}
    </div>
  );
}

export function Callout({ tone = 'info', children, title }: { tone?: 'info' | 'warn' | 'bad' | 'good'; children: ReactNode; title?: ReactNode }) {
  const c = { info: 'border-line bg-raised', warn: 'border-line-strong bg-raised', bad: 'border-bad/40', good: 'border-line' }[tone];
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${c}`}>
      {title && <div className="font-semibold text-ink">{title}</div>}
      <div className="text-muted">{children}</div>
    </div>
  );
}
