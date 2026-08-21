import { useEffect, useRef } from 'react';
import { Sparkles } from 'lucide-react';
import { useSession } from '@/context/SessionContext';
import { MessageBubble } from './MessageBubble';
import { InterruptCard } from '@/components/interrupt/InterruptCard';
import { CsvPreviewCard } from '@/components/csv_preview/CsvPreviewCard';
import { AnomalyChartCard } from '@/components/anomaly_chart/AnomalyChartCard';
import { TrainingProgressCard } from '@/components/anomaly_chart/TrainingProgressCard';
import { CorrelationHeatmapCard } from '@/components/analysis_chart/CorrelationHeatmapCard';
import { HistogramCard } from '@/components/analysis_chart/HistogramCard';
import { DecompositionChartCard } from '@/components/analysis_chart/DecompositionChartCard';
import { ControlChartCard } from '@/components/analysis_chart/ControlChartCard';
import { ChangePointChartCard } from '@/components/analysis_chart/ChangePointChartCard';
import { AcfChartCard } from '@/components/analysis_chart/AcfChartCard';
import { ForecastChartCard } from '@/components/forecast_chart/ForecastChartCard';
import { BacktestChartCard } from '@/components/forecast_chart/BacktestChartCard';
import type { AnalysisChart, PredictionChart } from '@/types';
import { cn } from '@/utils/cn';

/** Dispatch the 6 Tier-1 analysis-chart variants on ``chart_type``. */
function AnalysisChartCard({ chart }: { chart: AnalysisChart }) {
  switch (chart.chart_type) {
    case 'correlation_heatmap':
      return <CorrelationHeatmapCard chart={chart} />;
    case 'histogram':
      return <HistogramCard chart={chart} />;
    case 'decomposition':
      return <DecompositionChartCard chart={chart} />;
    case 'control_chart':
      return <ControlChartCard chart={chart} />;
    case 'changepoint':
      return <ChangePointChartCard chart={chart} />;
    case 'acf':
      return <AcfChartCard chart={chart} />;
    default:
      // Exhaustiveness guard — should never fire for a valid Tier-1 payload.
      return null;
  }
}

/** Dispatch the prediction-chart variants on ``chart_type``. The
 *  ``prediction_chart`` SSE channel carries both forecast (forecast
 *  family of tools) and backtest (evaluation family) payloads. */
function PredictionChartCard({ chart }: { chart: PredictionChart }) {
  switch (chart.chart_type) {
    case 'forecast':
      return <ForecastChartCard chart={chart} />;
    case 'backtest':
      return <BacktestChartCard chart={chart} />;
    default:
      return null;
  }
}

export function ChatView({ showEmptyState = true }: { showEmptyState?: boolean }) {
  const { items, streaming, sendQuery } = useSession();
  const scrollerRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  // Track whether the user has scrolled away from the bottom.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottomRef.current = distance < 80;
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  // Auto-scroll when new content arrives if user is at the bottom.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || !stickToBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [items, streaming]);

  const hasItems = items.length > 0;

  return (
    <div
      ref={scrollerRef}
      className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-10 py-6"
    >
      <div className="mx-auto w-full max-w-3xl">
        {!hasItems && showEmptyState && <EmptyState onPick={(p) => void sendQuery(p)} />}

        <div className="space-y-5">
          {items.map((item) => {
            if (item.kind === 'message') {
              return (
                <MessageBubble
                  key={item.id}
                  message={item.message}
                  streaming={streaming && item.message.role === 'assistant' && item.message.content === ''}
                />
              );
            }
            if (item.kind === 'interrupt') {
              return <InterruptCard key={item.id} item={item} />;
            }
            if (item.kind === 'csv_preview') {
              return <CsvPreviewCard key={item.id} preview={item.preview} />;
            }
            if (item.kind === 'anomaly_chart') {
              return <AnomalyChartCard key={item.id} chart={item.chart} />;
            }
            if (item.kind === 'anomaly_training_progress') {
              return (
                <TrainingProgressCard
                  key={item.id}
                  progress={item.progress}
                  history={item.history}
                />
              );
            }
            if (item.kind === 'prediction_finetuning_progress') {
              return (
                <TrainingProgressCard
                  key={item.id}
                  progress={item.progress}
                  history={item.history}
                />
              );
            }
            if (item.kind === 'analysis_chart') {
              return <AnalysisChartCard key={item.id} chart={item.chart} />;
            }
            if (item.kind === 'prediction_chart') {
              return <PredictionChartCard key={item.id} chart={item.chart} />;
            }
            // status
            return (
              <div
                key={item.id}
                className={cn(
                  'flex justify-center animate-fade-in',
                )}
              >
                <div
                  className={cn(
                    'rounded-full border px-3 py-1 text-[11px] font-medium',
                    item.tone === 'error'
                      ? 'border-rose-200 bg-rose-50 text-rose-700'
                      : item.tone === 'success'
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-steel-200 bg-white/80 text-steel-500',
                  )}
                >
                  {item.text}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  const suggestions = [
    '分析这份传感器数据的整体趋势',
    '检测该烘箱温度的异常时间段',
    '预测该气缸未来12个采样点的压力值',
    '涂布均匀性波动调控：箔材涂布厚度不均匀导致电池片性能不稳定，如何挖掘分析受其影响的关键参数？',
  ];
  return (
    <div className="mt-10 flex flex-col items-center text-center animate-fade-in">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-800 text-white shadow-glow">
        <Sparkles className="h-7 w-7" />
      </div>
      <h1 className="mt-5 text-xl font-semibold text-steel-900">
        工业时序分析 · 开始你的第一次对话
      </h1>
      <p className="mt-2 max-w-md text-sm text-steel-500">
        用自然语言描述你的分析需求。智能体会自动进行意图识别、数据画像、方案规划、参数确认与任务执行，
        并在关键节点向你请求人工确认。
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="rounded-full border border-steel-200 bg-white/80 px-3.5 py-1.5 text-xs text-steel-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
