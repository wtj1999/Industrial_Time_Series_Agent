import type { CSSProperties } from 'react';
import { Check, Factory, Network, Route, SunMoon } from 'lucide-react';
import './NgReportFlow.css';

export interface ReportFlowStage {
  key: 'device' | 'shift' | 'upstream'; name: string; reason: string; summary: string; insufficient: boolean;
}

const icons = { device: Factory, shift: SunMoon, upstream: Network };

export function NgReportFlow({ stages, activeStage }: { stages: ReportFlowStage[]; activeStage: number }) {
  return <section className="ng-report-flow" data-report-flow="true" aria-label="分析路径">
    <div className="ng-report-flow__header">
      <div className="ng-report-flow__heading"><Route size={16} aria-hidden="true" /><span>根因排查路径</span></div>
      <div className="ng-report-flow__position"><span className="ng-report-flow__status-dot" aria-hidden="true" />
        <span>当前 · {stages[activeStage].name}</span><span className="ng-report-flow__fraction">{String(activeStage + 1).padStart(2, '0')} / {String(stages.length).padStart(2, '0')}</span>
      </div>
    </div>
    <div className="ng-report-flow__diagram">
    <ol className="ng-report-flow__steps" aria-label="报告排查顺序">{stages.map((stage, index) => {
      const current = index === activeStage, reached = index <= activeStage, Icon = icons[stage.key];
      return <li key={stage.key} className="ng-report-flow__step" data-report-stage={stage.key}
        data-stage-state={current ? 'current' : reached ? 'completed' : 'pending'} data-stage-insufficient={reached && stage.insufficient ? 'true' : undefined}
        aria-current={current ? 'step' : undefined} style={{ '--ng-flow-delay': `${index * 75}ms` } as CSSProperties}>
        <div className="ng-report-flow__card">
          <div className="ng-report-flow__node-header">
            <div className="ng-report-flow__icon"><Icon size={19} strokeWidth={1.7} aria-hidden="true" />
              {!current && reached ? <span className="ng-report-flow__completion" aria-hidden="true">{stage.insufficient ? '?' : <Check size={10} strokeWidth={2.5} />}</span> : null}
            </div>
            <span className="ng-report-flow__name">{stage.name}</span>
            <span className="ng-report-flow__number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
          </div>
          {reached ? <p data-stage-result="true" className="ng-report-flow__result" title={stage.reason}>{stage.summary}</p> : null}
        </div>
        {index < stages.length - 1 ? <span className="ng-report-flow__connector" data-report-connector="true" data-traversed={index < activeStage ? 'true' : 'false'} aria-hidden="true">
          <span className="ng-report-flow__link">{index < activeStage ? <span className="ng-report-flow__signal" /> : null}</span>
          <svg className="ng-report-flow__arrowhead" width="8" height="12" viewBox="0 0 8 12" fill="none">
            <path d="M1 1L6 6L1 11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span> : null}
      </li>;
    })}</ol></div>
  </section>;
}
