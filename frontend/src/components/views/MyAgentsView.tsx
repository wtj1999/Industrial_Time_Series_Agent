import { useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Activity,
  BatteryCharging,
  Bot,
  ChartSpline,
  Factory,
  CarFront,
  Store,
  ScanSearch,
  Wrench,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { useSession } from '@/context/SessionContext';
import { BatteryInstallationForecastApp } from '@/features/agent-apps/battery-installation-forecast/BatteryInstallationForecastApp';
import { BATTERY_INSTALLATION_AGENT } from '@/features/agent-apps/battery-installation-forecast/config';
import { NewEnergyVehicleSalesApp } from '@/features/agent-apps/new-energy-vehicle-sales/NewEnergyVehicleSalesApp';
import { NEW_ENERGY_VEHICLE_SALES_AGENT } from '@/features/agent-apps/new-energy-vehicle-sales/config';
import { CoatingArealDensityAnalysisApp } from '@/features/agent-apps/coating-areal-density-analysis/CoatingArealDensityAnalysisApp';
import { COATING_AREAL_DENSITY_AGENT } from '@/features/agent-apps/coating-areal-density-analysis/config';
import { CoatingArealDensityAnomalyDetectionApp } from '@/features/agent-apps/coating-areal-density-anomaly-detection/CoatingArealDensityAnomalyDetectionApp';
import { COATING_AREAL_DENSITY_ANOMALY_AGENT } from '@/features/agent-apps/coating-areal-density-anomaly-detection/config';

type AgentDomain = 'equipment' | 'production' | 'market';

const DOMAIN_COUNTS: Record<AgentDomain, number> = {
  equipment: 2,
  production: 0,
  market: 2,
};

const DOMAIN_META: Record<
  AgentDomain,
  {
    title: string;
    description: string;
    icon: typeof Bot;
    border: string;
    orb: string;
    iconWrap: string;
    ring: string;
  }
> = {
  equipment: {
    title: '设备域',
    description: '面向设备状态监测、故障诊断、预测性维护等场景的智能体。',
    icon: Wrench,
    border: 'border-cyan-200/80 hover:border-cyan-400',
    orb: 'bg-cyan-50',
    iconWrap: 'bg-cyan-100 text-cyan-700',
    ring: 'focus-visible:ring-cyan-500',
  },
  production: {
    title: '生产域',
    description: '面向生产过程分析、质量控制、产能优化等场景的智能体。',
    icon: Factory,
    border: 'border-emerald-200/80 hover:border-emerald-400',
    orb: 'bg-emerald-50',
    iconWrap: 'bg-emerald-100 text-emerald-700',
    ring: 'focus-visible:ring-emerald-500',
  },
  market: {
    title: '市场域',
    description: '面向市场趋势洞察、销量预测、需求分析等场景的智能体。',
    icon: Store,
    border: 'border-amber-200/80 hover:border-amber-400',
    orb: 'bg-amber-50',
    iconWrap: 'bg-amber-100 text-amber-700',
    ring: 'focus-visible:ring-amber-500',
  },
};

export function MyAgentsView({ onBack }: { onBack: () => void }) {
  const { initNewSession } = useSession();
  const [activeDomain, setActiveDomain] = useState<AgentDomain | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const activeMeta = activeDomain ? DOMAIN_META[activeDomain] : null;
  const visibleCount = activeDomain
    ? DOMAIN_COUNTS[activeDomain]
    : Object.values(DOMAIN_COUNTS).reduce((total, count) => total + count, 0);

  const handleBack = () => {
    if (activeAgent) {
      setActiveAgent(null);
    } else if (activeDomain) {
      setActiveDomain(null);
    } else {
      onBack();
    }
  };

  const openBatteryAgent = () => {
    initNewSession();
    setActiveAgent(BATTERY_INSTALLATION_AGENT.id);
  };

  const openVehicleSalesAgent = () => {
    initNewSession();
    setActiveAgent(NEW_ENERGY_VEHICLE_SALES_AGENT.id);
  };

  const openCoatingAgent = () => {
    initNewSession();
    setActiveAgent(COATING_AREAL_DENSITY_AGENT.id);
  };

  const openCoatingAnomalyAgent = () => {
    initNewSession();
    setActiveAgent(COATING_AREAL_DENSITY_ANOMALY_AGENT.id);
  };

  const activeAgentName = activeAgent === NEW_ENERGY_VEHICLE_SALES_AGENT.id
    ? NEW_ENERGY_VEHICLE_SALES_AGENT.name
    : activeAgent === COATING_AREAL_DENSITY_AGENT.id
      ? COATING_AREAL_DENSITY_AGENT.name
      : activeAgent === COATING_AREAL_DENSITY_ANOMALY_AGENT.id
        ? COATING_AREAL_DENSITY_ANOMALY_AGENT.name
      : BATTERY_INSTALLATION_AGENT.name;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-steel-200/70 bg-white/60 px-4 py-3 backdrop-blur-md sm:px-6">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900"
          title={activeAgent
            ? `返回${activeDomain === 'equipment' ? '设备域' : '市场域'}`
            : activeDomain ? '返回智能体分类' : '返回对话'}
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-cyan-700 text-white">
            <Bot className="h-3.5 w-3.5" />
          </span>
          <h1 className="text-sm font-semibold text-steel-800">
            {activeAgent ? activeAgentName : activeMeta?.title ?? '我的智能体'}
          </h1>
          {!activeAgent && (
            <span className="rounded-full bg-steel-100 px-2 py-0.5 text-[10px] font-medium text-steel-600">
              {visibleCount} 个智能体
            </span>
          )}
        </div>
      </div>

      {activeAgent ? (
        activeAgent === NEW_ENERGY_VEHICLE_SALES_AGENT.id
          ? <NewEnergyVehicleSalesApp />
          : activeAgent === COATING_AREAL_DENSITY_AGENT.id
            ? <CoatingArealDensityAnalysisApp />
            : activeAgent === COATING_AREAL_DENSITY_ANOMALY_AGENT.id
              ? <CoatingArealDensityAnomalyDetectionApp />
            : <BatteryInstallationForecastApp />
      ) : (
        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="mx-auto w-full max-w-5xl">
          {activeDomain === 'market' ? (
            <MarketAgents
              onOpenBatteryAgent={openBatteryAgent}
              onOpenVehicleSalesAgent={openVehicleSalesAgent}
            />
          ) : activeDomain === 'equipment' ? (
            <EquipmentAgents onOpenCoatingAgent={openCoatingAgent} onOpenCoatingAnomalyAgent={openCoatingAnomalyAgent} />
          ) : activeDomain ? (
            <DomainEmptyState domain={activeDomain} />
          ) : (
            <DomainGrid onSelect={setActiveDomain} />
          )}
          </div>
        </div>
      )}
    </div>
  );
}

function EquipmentAgents({ onOpenCoatingAgent, onOpenCoatingAnomalyAgent }: { onOpenCoatingAgent: () => void; onOpenCoatingAnomalyAgent: () => void }) {
  return (
    <div>
      <p className="mb-4 text-xs text-steel-500">{DOMAIN_META.equipment.description}</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <button
          type="button"
          onClick={onOpenCoatingAgent}
          className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-cyan-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-cyan-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-cyan-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cyan-100 text-cyan-700"><Activity className="h-5 w-5" /></span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电涂布面密度分析智能体</h3>
              <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50 px-2 py-0.5 text-[9px] font-medium text-cyan-700"><ChartSpline className="h-3 w-3" />时序分析</span>
            </div>
          </div>
          <p className="relative mt-4 text-xs leading-5 text-steel-500">分析涂布面密度的稳定性、控制状态、过程能力、漂移、变点与分区关联。</p>
          <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-cyan-700">配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
        </button>
        <button
          type="button"
          onClick={onOpenCoatingAnomalyAgent}
          className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-violet-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-violet-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-violet-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-violet-700"><ScanSearch className="h-5 w-5" /></span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电涂布面密度异常检测智能体</h3>
              <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[9px] font-medium text-violet-700"><Activity className="h-3 w-3" />异常检测</span>
            </div>
          </div>
          <p className="relative mt-4 text-xs leading-5 text-steel-500">检测涂布面密度的异常时间点、连续异常区间及主要异常分区。</p>
          <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-violet-700">配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
        </button>
      </div>
    </div>
  );
}

function DomainGrid({ onSelect }: { onSelect: (domain: AgentDomain) => void }) {
  return (
    <div>
      <div className="mb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-steel-400">
          智能体资产
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-steel-900">
          按业务领域浏览
        </h2>
        <p className="mt-1 text-xs text-steel-500">
          选择智能体所属的业务领域，再查看和管理具体智能体。
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {(Object.keys(DOMAIN_META) as AgentDomain[]).map((domain) => {
          const meta = DOMAIN_META[domain];
          const Icon = meta.icon;

          return (
            <button
              key={domain}
              type="button"
              onClick={() => onSelect(domain)}
              className={cn(
                'group relative min-h-[190px] overflow-hidden rounded-2xl border bg-white p-5 text-left shadow-sm transition-all',
                'hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
                meta.border,
                meta.ring,
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  'absolute -right-10 -top-12 h-36 w-36 rounded-full opacity-60 transition-transform duration-300 group-hover:scale-110',
                  meta.orb,
                )}
              />
              <div className="relative flex h-full flex-col">
                <div className="flex items-start justify-between gap-4">
                  <span className={cn('flex h-11 w-11 items-center justify-center rounded-xl', meta.iconWrap)}>
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="flex items-center gap-1 text-[11px] font-medium text-steel-500">
                    {DOMAIN_COUNTS[domain]} 个智能体
                    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </div>
                <h3 className="mt-6 text-base font-semibold text-steel-900">{meta.title}</h3>
                <p className="mt-1.5 text-xs leading-5 text-steel-500">{meta.description}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function MarketAgents({
  onOpenBatteryAgent,
  onOpenVehicleSalesAgent,
}: {
  onOpenBatteryAgent: () => void;
  onOpenVehicleSalesAgent: () => void;
}) {
  return (
    <div>
      <p className="mb-4 text-xs text-steel-500">{DOMAIN_META.market.description}</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <button
          type="button"
          onClick={onOpenBatteryAgent}
          className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-amber-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-amber-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
        >
          <span
            aria-hidden="true"
            className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-amber-50 opacity-70 transition-transform duration-300 group-hover:scale-110"
          />
          <div className="relative flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
              <BatteryCharging className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[13px] font-semibold leading-5 text-steel-800">
                动力电池装车量预测智能体
              </h3>
              <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[9px] font-medium text-amber-700">
                <ChartSpline className="h-3 w-3" />
                时序预测
              </span>
            </div>
          </div>
          <p className="relative mt-4 text-xs leading-5 text-steel-500">
            基于历史装车量与市场数据，分析变化趋势并预测未来动力电池装车量。
          </p>
          <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-amber-700">
            配置任务
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </span>
        </button>
        <button
          type="button"
          onClick={onOpenVehicleSalesAgent}
          className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-blue-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-blue-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-blue-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
              <CarFront className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[13px] font-semibold leading-5 text-steel-800">新能源汽车销量预测智能体</h3>
              <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[9px] font-medium text-blue-700">
                <ChartSpline className="h-3 w-3" />时序预测
              </span>
            </div>
          </div>
          <p className="relative mt-4 text-xs leading-5 text-steel-500">
            基于历史销量与市场影响因素，预测新能源汽车未来销量及细分市场趋势。
          </p>
          <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-blue-700">
            配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </span>
        </button>
      </div>
    </div>
  );
}

function DomainEmptyState({ domain }: { domain: AgentDomain }) {
  const meta = DOMAIN_META[domain];
  const Icon = meta.icon;

  return (
    <div className="flex min-h-[360px] items-center justify-center">
      <div className="max-w-sm text-center">
        <span className={cn('mx-auto flex h-14 w-14 items-center justify-center rounded-2xl', meta.iconWrap)}>
          <Icon className="h-6 w-6" />
        </span>
        <h2 className="mt-4 text-sm font-semibold text-steel-800">
          {meta.title}还没有智能体
        </h2>
        <p className="mt-1.5 text-xs leading-5 text-steel-500">{meta.description}</p>
      </div>
    </div>
  );
}
