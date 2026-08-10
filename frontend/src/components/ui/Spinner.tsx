import { cn } from '@/utils/cn';

export function Spinner({
  className,
  label,
}: {
  className?: string;
  label?: string;
}) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)} role="status" aria-live="polite">
      <svg
        className={cn('animate-spin text-brand-500', className)}
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden
      >
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2" />
        <path
          d="M12 2a10 10 0 0 1 10 10"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      {label && <span className="text-xs text-steel-500">{label}</span>}
    </span>
  );
}

/** Three-dot typing indicator for the assistant. */
export function TypingDots({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1', className)} aria-hidden>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-steel-400 animate-pulse-soft"
          style={{ animationDelay: `${i * 160}ms` }}
        />
      ))}
    </span>
  );
}
