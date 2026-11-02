import { Lightbulb, Sparkles } from 'lucide-react';
import type { NgAnalysis } from '../production-bi-analysis/types';

export function NgAnalysisCard({ analysis }: { analysis: NgAnalysis }) {
  return (
    <section aria-label="分析与建议" className="break-words rounded-xl border border-emerald-100 bg-gradient-to-br from-emerald-50/60 to-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Sparkles className="h-4 w-4 text-emerald-600" />
        <h4 className="text-sm font-semibold text-steel-900">分析与建议</h4>
        <span className="text-[10px] text-steel-500">基于本次全部查询结果</span>
      </div>
      {analysis.status === 'success' ? (
        <div className="mt-3 space-y-4 text-xs leading-6 text-steel-700">
          <p className="whitespace-pre-wrap text-sm leading-6 text-steel-800">{analysis.summary}</p>
          <div>
            <h5 className="mb-2 font-semibold text-steel-900">数据观察</h5>
            <ul className="space-y-2">
              {analysis.findings.map((finding, index) => (
                <li key={index} className="border-l-2 border-emerald-300 pl-3">
                  <p className="font-medium text-steel-800">{finding.title}</p>
                  <p className="whitespace-pre-wrap">{finding.detail}</p>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h5 className="mb-2 flex items-center gap-1.5 font-semibold text-steel-900">
              <Lightbulb className="h-3.5 w-3.5 text-emerald-600" />排查与改善建议
            </h5>
            <ol className="space-y-2.5">
              {analysis.recommendations.map((recommendation, index) => (
                <li key={index} className="rounded-lg border border-steel-200/70 bg-white/80 px-3 py-2.5">
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0 rounded bg-emerald-100 px-1.5 text-[10px] font-medium leading-5 text-emerald-700">
                      {recommendation.priority}优先
                    </span>
                    <p className="whitespace-pre-wrap">{recommendation.action}</p>
                  </div>
                  <p className="mt-1.5 whitespace-pre-wrap text-[11px] leading-5 text-steel-500">验证方式：{recommendation.verification}</p>
                </li>
              ))}
            </ol>
          </div>
          {analysis.limitations.length > 0 && (
            <div className="border-t border-emerald-100 pt-2.5 text-[11px] leading-5 text-steel-500">
              <p className="font-medium text-steel-600">分析边界</p>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {analysis.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <p role="status" className="mt-3 text-xs leading-6 text-steel-500">{analysis.message}</p>
      )}
    </section>
  );
}
