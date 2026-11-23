import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

export function NgMetricTooltipCell({ label, children, explanation }: { label: string; children: ReactNode; explanation: ReactNode }) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const tooltip = useRef<HTMLDivElement>(null);
  const closing = useRef<number>();
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  const clearClosing = () => window.clearTimeout(closing.current);
  const hide = () => { clearClosing(); setOpen(false); setPosition(null); };
  const show = () => { clearClosing(); setOpen(true); };
  const closeSoon = () => { clearClosing(); closing.current = window.setTimeout(hide, 120); };

  useEffect(() => () => window.clearTimeout(closing.current), []);
  useEffect(() => {
    if (!open || !trigger.current || !tooltip.current) return;
    const anchor = trigger.current.getBoundingClientRect();
    const bubble = tooltip.current.getBoundingClientRect();
    const left = Math.max(8, Math.min(anchor.left + anchor.width / 2 - bubble.width / 2, window.innerWidth - bubble.width - 8));
    const preferredTop = anchor.bottom + 8 + bubble.height <= window.innerHeight - 8 ? anchor.bottom + 8 : anchor.top - bubble.height - 8;
    const top = Math.max(8, Math.min(preferredTop, window.innerHeight - bubble.height - 8));
    setPosition({ left, top });
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !trigger.current?.contains(event.target) && !tooltip.current?.contains(event.target)) hide();
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.stopPropagation(); hide(); }
    };
    const scroll = (event: Event) => {
      if (!(event.target instanceof Node) || !tooltip.current?.contains(event.target)) hide();
    };
    document.addEventListener('pointerdown', outside, true);
    document.addEventListener('keydown', escape, true);
    window.addEventListener('scroll', scroll, true);
    window.addEventListener('resize', hide);
    return () => {
      document.removeEventListener('pointerdown', outside, true);
      document.removeEventListener('keydown', escape, true);
      window.removeEventListener('scroll', scroll, true);
      window.removeEventListener('resize', hide);
    };
  }, [open, explanation]);

  return <td className="px-2 py-2" onPointerEnter={event => { if (event.pointerType === 'mouse') show(); }} onPointerLeave={event => { if (event.pointerType === 'mouse') closeSoon(); }}>
    <button ref={trigger} type="button" aria-label={label} aria-describedby={open ? id : undefined}
      onFocus={show} onBlur={closeSoon} onClick={show}
      className="block w-full cursor-help rounded text-left underline decoration-steel-300 decoration-dotted underline-offset-4 outline-none focus-visible:ring-2 focus-visible:ring-emerald-500">
      {children}
    </button>
    {open && createPortal(<div ref={tooltip} id={id} role="tooltip" aria-label={label}
      className="fixed z-[80] overflow-y-auto rounded-xl border border-steel-200 bg-white p-3 text-xs leading-5 shadow-lg"
      style={{ width: 'min(380px, calc(100vw - 16px))', maxHeight: 'calc(100vh - 16px)', left: position?.left ?? 0, top: position?.top ?? 0, visibility: position ? 'visible' : 'hidden' }}
      onPointerEnter={clearClosing} onPointerLeave={closeSoon}>
      <p className="mb-1.5 break-words font-medium text-steel-800">{label}</p>
      {explanation}
    </div>, document.body)}
  </td>;
}
