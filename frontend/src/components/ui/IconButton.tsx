import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { className, children, active, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
        'inline-flex h-9 w-9 items-center justify-center rounded-lg text-steel-500 transition-colors',
        'hover:bg-steel-100 hover:text-steel-800',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        active && 'bg-brand-50 text-brand-700 hover:bg-brand-100 hover:text-brand-800',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
});
