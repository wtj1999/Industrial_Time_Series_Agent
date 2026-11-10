import type { ReactNode } from 'react';
import { ArrowRight, type LucideIcon } from 'lucide-react';

/** A single card surface for domain entries, factory directories and apps. */
export function CatalogCard({ title, description, subtitle, icon: Icon, index, kind, action = '进入目录', className = '', onClick, children }: {
 title: string; description: string; subtitle?: string; icon: LucideIcon;
 index: number; kind: string; action?: string; className?: string;
 onClick: () => void; children?: ReactNode;
}) {
 return <button type="button" className={`production-directory-card ${className}`} onClick={onClick}>
  <div className="production-card-top"><span className="production-card-index">{String(index+1).padStart(2,'0')} / {kind}</span><span className="production-card-symbol"><Icon size={22} strokeWidth={1.5}/></span></div>
  <div className="production-card-copy">{subtitle && <span className="production-card-kicker">{subtitle}</span>}<h3 title={title}>{title}</h3><p title={description}>{description}</p></div>
  {children}
  <span className="production-card-footer"><span>{action}</span><span className="production-card-arrow"><ArrowRight size={17}/></span></span>
 </button>;
}
