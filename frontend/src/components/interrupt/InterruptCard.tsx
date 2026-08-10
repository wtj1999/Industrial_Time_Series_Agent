import { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  UploadCloud,
} from 'lucide-react';
import type { ConversationItem } from '@/context/SessionContext';
import { useSession } from '@/context/SessionContext';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/utils/cn';
import { TechPathSelector } from './TechPathSelector';
import { CsvUploadPanel } from './CsvUploadPanel';
import { ClarificationPanel } from './ClarificationPanel';

const TYPE_META: Record<
  string,
  { label: string; tone: 'brand' | 'warning' | 'info'; icon: typeof HelpCircle }
> = {
  choose_tech_path: { label: '选择技术方案', tone: 'brand', icon: AlertTriangle },
  upload_csv: { label: '请上传数据文件', tone: 'warning', icon: UploadCloud },
  clarification: { label: '请确认字段映射', tone: 'info', icon: HelpCircle },
};

export function InterruptCard({ item }: { item: Extract<ConversationItem, { kind: 'interrupt' }> }) {
  const { interrupt } = item;
  const meta = TYPE_META[interrupt.type] ?? {
    label: '人工确认',
    tone: 'info' as const,
    icon: HelpCircle,
  };
  const Icon = meta.icon;

  const submitted = item.status === 'submitted';
  const [collapsed, setCollapsed] = useState(submitted);

  return (
    <div
      className={cn(
        'rounded-2xl border shadow-soft animate-slide-up overflow-hidden',
        submitted ? 'border-emerald-200 bg-emerald-50/30' : 'border-brand-200 bg-white',
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 px-4 sm:px-5 py-3 border-b border-steel-200/70 bg-gradient-to-r from-brand-50/60 to-transparent">
        <div
          className={cn(
            'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg shadow-sm',
            meta.tone === 'brand' && 'bg-brand-600 text-white',
            meta.tone === 'warning' && 'bg-amber-500 text-white',
            meta.tone === 'info' && 'bg-sky-500 text-white',
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-steel-900">
              {meta.label}
            </h3>
            <Badge tone={submitted ? 'success' : meta.tone}>
              {submitted ? '已响应' : '等待你的输入'}
            </Badge>
            {'message' in interrupt && interrupt.message && (
              <span className="text-xs text-steel-500 truncate">· {interrupt.message}</span>
            )}
          </div>
        </div>
        {submitted && (
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="rounded p-1 text-steel-400 hover:bg-steel-100 hover:text-steel-700"
            aria-label={collapsed ? '展开' : '收起'}
          >
            {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="p-4 sm:p-5">
          {submitted ? (
            <SubmittedNotice />
          ) : interrupt.type === 'choose_tech_path' ? (
            <TechPathSelector interrupt={interrupt} />
          ) : interrupt.type === 'upload_csv' ? (
            <CsvUploadPanel interrupt={interrupt} />
          ) : interrupt.type === 'clarification' ? (
            <ClarificationPanel interrupt={interrupt} />
          ) : (
            <FallbackNotice type={(interrupt as { type?: string }).type ?? 'unknown'} />
          )}
        </div>
      )}
    </div>
  );
}

function SubmittedNotice() {
  return (
    <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
      <CheckCircle2 className="h-4 w-4" />
      已提交响应，智能体正在继续执行…
    </div>
  );
}

function FallbackNotice({ type }: { type: string }) {
  const { dismissInterrupt } = useSession();
  return (
    <div className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700 flex items-center justify-between gap-3">
      <span>未识别的中断类型：<code className="font-mono">{type}</code></span>
      <button
        onClick={dismissInterrupt}
        className="rounded-md border border-rose-200 bg-white px-2 py-1 text-[11px] hover:bg-rose-100"
      >
        关闭
      </button>
    </div>
  );
}
