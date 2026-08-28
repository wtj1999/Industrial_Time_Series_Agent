import { useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Activity,
  BatteryCharging,
  BatteryWarning,
  Boxes,
  Bot,
  ChartSpline,
  Factory,
  CarFront,
  Coins,
  Disc3,
  Flame,
  Gauge,
  Store,
  ScanSearch,
  Wrench,
  Zap,
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
import { CellCapacityRootCauseApp } from '@/features/agent-apps/cell-capacity-root-cause/CellCapacityRootCauseApp';
import { CELL_CAPACITY_ROOT_CAUSE_AGENT } from '@/features/agent-apps/cell-capacity-root-cause/config';
import { CellProductionForecastApp } from '@/features/agent-apps/cell-production-forecast/CellProductionForecastApp';
import { CELL_PRODUCTION_FORECAST_AGENT } from '@/features/agent-apps/cell-production-forecast/config';
import { PackProductionForecastApp } from '@/features/agent-apps/pack-production-forecast/PackProductionForecastApp';
import { PACK_PRODUCTION_FORECAST_AGENT } from '@/features/agent-apps/pack-production-forecast/config';
import { FactoryEnergyForecastApp } from '@/features/agent-apps/factory-energy-forecast/FactoryEnergyForecastApp';
import { FACTORY_ENERGY_FORECAST_AGENT } from '@/features/agent-apps/factory-energy-forecast/config';
import { RawMaterialPriceForecastApp } from '@/features/agent-apps/raw-material-price-forecast/RawMaterialPriceForecastApp';
import { RAW_MATERIAL_PRICE_FORECAST_AGENT } from '@/features/agent-apps/raw-material-price-forecast/config';
import { CylinderEquipmentAnomalyDetectionApp } from '@/features/agent-apps/cylinder-equipment-anomaly-detection/CylinderEquipmentAnomalyDetectionApp';
import { CYLINDER_EQUIPMENT_ANOMALY_AGENT } from '@/features/agent-apps/cylinder-equipment-anomaly-detection/config';
import { ServoMotorAnomalyDetectionApp } from '@/features/agent-apps/servo-motor-anomaly-detection/ServoMotorAnomalyDetectionApp';
import { SERVO_MOTOR_ANOMALY_AGENT } from '@/features/agent-apps/servo-motor-anomaly-detection/config';
import { WeldingEquipmentAnomalyDetectionApp } from '@/features/agent-apps/welding-equipment-anomaly-detection/WeldingEquipmentAnomalyDetectionApp';
import { WELDING_EQUIPMENT_ANOMALY_AGENT } from '@/features/agent-apps/welding-equipment-anomaly-detection/config';

type AgentDomain = 'equipment' | 'production' | 'market';

const DOMAIN_COUNTS: Record<AgentDomain, number> = {
  equipment: 6,
  production: 3,
  market: 3,
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

  const openRawMaterialPriceForecastAgent = () => {
    initNewSession();
    setActiveAgent(RAW_MATERIAL_PRICE_FORECAST_AGENT.id);
  };

  const openCoatingAgent = () => {
    initNewSession();
    setActiveAgent(COATING_AREAL_DENSITY_AGENT.id);
  };

  const openCoatingAnomalyAgent = () => {
    initNewSession();
    setActiveAgent(COATING_AREAL_DENSITY_ANOMALY_AGENT.id);
  };

  const openCylinderAnomalyAgent = () => {
    initNewSession();
    setActiveAgent(CYLINDER_EQUIPMENT_ANOMALY_AGENT.id);
  };

  const openServoMotorAnomalyAgent = () => {
    initNewSession();
    setActiveAgent(SERVO_MOTOR_ANOMALY_AGENT.id);
  };

  const openWeldingAnomalyAgent = () => {
    initNewSession();
    setActiveAgent(WELDING_EQUIPMENT_ANOMALY_AGENT.id);
  };

  const openCellCapacityRootCauseAgent = () => {
    initNewSession();
    setActiveAgent(CELL_CAPACITY_ROOT_CAUSE_AGENT.id);
  };

  const openCellProductionForecastAgent = () => {
    initNewSession();
    setActiveAgent(CELL_PRODUCTION_FORECAST_AGENT.id);
  };

  const openPackProductionForecastAgent = () => {
    initNewSession();
    setActiveAgent(PACK_PRODUCTION_FORECAST_AGENT.id);
  };

  const openFactoryEnergyForecastAgent = () => {
    initNewSession();
    setActiveAgent(FACTORY_ENERGY_FORECAST_AGENT.id);
  };

  const activeAgentName = activeAgent === NEW_ENERGY_VEHICLE_SALES_AGENT.id
    ? NEW_ENERGY_VEHICLE_SALES_AGENT.name
    : activeAgent === RAW_MATERIAL_PRICE_FORECAST_AGENT.id
      ? RAW_MATERIAL_PRICE_FORECAST_AGENT.name
    : activeAgent === COATING_AREAL_DENSITY_AGENT.id
      ? COATING_AREAL_DENSITY_AGENT.name
      : activeAgent === COATING_AREAL_DENSITY_ANOMALY_AGENT.id
        ? COATING_AREAL_DENSITY_ANOMALY_AGENT.name
        : activeAgent === CYLINDER_EQUIPMENT_ANOMALY_AGENT.id
          ? CYLINDER_EQUIPMENT_ANOMALY_AGENT.name
          : activeAgent === SERVO_MOTOR_ANOMALY_AGENT.id
            ? SERVO_MOTOR_ANOMALY_AGENT.name
            : activeAgent === WELDING_EQUIPMENT_ANOMALY_AGENT.id
              ? WELDING_EQUIPMENT_ANOMALY_AGENT.name
        : activeAgent === CELL_CAPACITY_ROOT_CAUSE_AGENT.id
          ? CELL_CAPACITY_ROOT_CAUSE_AGENT.name
          : activeAgent === CELL_PRODUCTION_FORECAST_AGENT.id
            ? CELL_PRODUCTION_FORECAST_AGENT.name
            : activeAgent === PACK_PRODUCTION_FORECAST_AGENT.id
              ? PACK_PRODUCTION_FORECAST_AGENT.name
              : activeAgent === FACTORY_ENERGY_FORECAST_AGENT.id
                ? FACTORY_ENERGY_FORECAST_AGENT.name
                : BATTERY_INSTALLATION_AGENT.name;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-steel-200/70 bg-white/60 px-4 py-3 backdrop-blur-md sm:px-6">
        <button
          type="button"
          onClick={handleBack}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900"
          title={activeAgent
            ? `返回${activeMeta?.title ?? '智能体列表'}`
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
          : activeAgent === RAW_MATERIAL_PRICE_FORECAST_AGENT.id
            ? <RawMaterialPriceForecastApp />
          : activeAgent === COATING_AREAL_DENSITY_AGENT.id
            ? <CoatingArealDensityAnalysisApp />
            : activeAgent === COATING_AREAL_DENSITY_ANOMALY_AGENT.id
              ? <CoatingArealDensityAnomalyDetectionApp />
              : activeAgent === CYLINDER_EQUIPMENT_ANOMALY_AGENT.id
                ? <CylinderEquipmentAnomalyDetectionApp />
                : activeAgent === SERVO_MOTOR_ANOMALY_AGENT.id
                  ? <ServoMotorAnomalyDetectionApp />
                  : activeAgent === WELDING_EQUIPMENT_ANOMALY_AGENT.id
                    ? <WeldingEquipmentAnomalyDetectionApp />
              : activeAgent === CELL_CAPACITY_ROOT_CAUSE_AGENT.id
                ? <CellCapacityRootCauseApp />
                : activeAgent === CELL_PRODUCTION_FORECAST_AGENT.id
                  ? <CellProductionForecastApp />
                  : activeAgent === PACK_PRODUCTION_FORECAST_AGENT.id
                    ? <PackProductionForecastApp />
                    : activeAgent === FACTORY_ENERGY_FORECAST_AGENT.id
                      ? <FactoryEnergyForecastApp />
                      : <BatteryInstallationForecastApp />
      ) : (
        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="mx-auto w-full max-w-5xl">
          {activeDomain === 'market' ? (
            <MarketAgents
              onOpenBatteryAgent={openBatteryAgent}
              onOpenVehicleSalesAgent={openVehicleSalesAgent}
              onOpenRawMaterialPriceForecastAgent={openRawMaterialPriceForecastAgent}
            />
          ) : activeDomain === 'equipment' ? (
            <EquipmentAgents
              onOpenCoatingAgent={openCoatingAgent}
              onOpenCoatingAnomalyAgent={openCoatingAnomalyAgent}
              onOpenCylinderAnomalyAgent={openCylinderAnomalyAgent}
              onOpenServoMotorAnomalyAgent={openServoMotorAnomalyAgent}
              onOpenWeldingAnomalyAgent={openWeldingAnomalyAgent}
              onOpenCellCapacityRootCauseAgent={openCellCapacityRootCauseAgent}
            />
          ) : activeDomain === 'production' ? (
            <ProductionAgents
              onOpenCellProductionForecastAgent={openCellProductionForecastAgent}
              onOpenPackProductionForecastAgent={openPackProductionForecastAgent}
              onOpenFactoryEnergyForecastAgent={openFactoryEnergyForecastAgent}
            />
          ) : (
            <DomainGrid onSelect={setActiveDomain} />
          )}
          </div>
        </div>
      )}
    </div>
  );
}

function ProductionAgents({
  onOpenCellProductionForecastAgent,
  onOpenPackProductionForecastAgent,
  onOpenFactoryEnergyForecastAgent,
}: {
  onOpenCellProductionForecastAgent: () => void;
  onOpenPackProductionForecastAgent: () => void;
  onOpenFactoryEnergyForecastAgent: () => void;
}) {
  return <div>
    <p className="mb-4 text-xs text-steel-500">{DOMAIN_META.production.description}</p>
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <button
        type="button"
        onClick={onOpenCellProductionForecastAgent}
        className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-emerald-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-emerald-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
      >
        <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-emerald-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
        <div className="relative flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700"><Factory className="h-5 w-5" /></span>
          <div className="min-w-0 flex-1">
            <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电电芯产量预测智能体</h3>
            <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[9px] font-medium text-emerald-700"><ChartSpline className="h-3 w-3" />时序预测</span>
          </div>
        </div>
        <p className="relative mt-4 text-xs leading-5 text-steel-500">结合历史产量、产线运行与质量数据，预测未来电芯产量及潜在产能缺口。</p>
        <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-emerald-700">配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
      </button>
      <button
        type="button"
        onClick={onOpenPackProductionForecastAgent}
        className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-teal-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-teal-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2"
      >
        <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-teal-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
        <div className="relative flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-100 text-teal-700"><Boxes className="h-5 w-5" /></span>
          <div className="min-w-0 flex-1">
            <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电PACK产量预测智能体</h3>
            <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-teal-200 bg-teal-50 px-2 py-0.5 text-[9px] font-medium text-teal-700"><ChartSpline className="h-3 w-3" />时序预测</span>
          </div>
        </div>
        <p className="relative mt-4 text-xs leading-5 text-steel-500">结合电芯齐套、PACK产线运行与质量数据，预测未来PACK产量及产能缺口。</p>
        <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-teal-700">配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
      </button>
      <button
        type="button"
        onClick={onOpenFactoryEnergyForecastAgent}
        className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-amber-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-amber-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
      >
        <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-amber-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
        <div className="relative flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700"><Zap className="h-5 w-5" /></span>
          <div className="min-w-0 flex-1">
            <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电工厂能耗预测智能体</h3>
            <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[9px] font-medium text-amber-700"><ChartSpline className="h-3 w-3" />时序预测</span>
          </div>
        </div>
        <p className="relative mt-4 text-xs leading-5 text-steel-500">结合各工段、公共设备和生产负荷数据，预测工厂未来能耗及单位产量能耗变化。</p>
        <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-amber-700">配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
      </button>
    </div>
  </div>;
}

function EquipmentAgents({
  onOpenCoatingAgent,
  onOpenCoatingAnomalyAgent,
  onOpenCylinderAnomalyAgent,
  onOpenServoMotorAnomalyAgent,
  onOpenWeldingAnomalyAgent,
  onOpenCellCapacityRootCauseAgent,
}: {
  onOpenCoatingAgent: () => void;
  onOpenCoatingAnomalyAgent: () => void;
  onOpenCylinderAnomalyAgent: () => void;
  onOpenServoMotorAnomalyAgent: () => void;
  onOpenWeldingAnomalyAgent: () => void;
  onOpenCellCapacityRootCauseAgent: () => void;
}) {
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
        <button
          type="button"
          onClick={onOpenCellCapacityRootCauseAgent}
          className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-rose-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-rose-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-rose-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-100 text-rose-700"><BatteryWarning className="h-5 w-5" /></span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电分容容量偏低根因分析智能体</h3>
              <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[9px] font-medium text-rose-700"><ScanSearch className="h-3 w-3" />根因分析</span>
            </div>
          </div>
          <p className="relative mt-4 text-xs leading-5 text-steel-500">基于分容容量与全流程工艺参数，定位容量偏低的关键影响因素并提供验证建议。</p>
          <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-rose-700">配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
        </button>
        <button
          type="button"
          onClick={onOpenCylinderAnomalyAgent}
          className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-indigo-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-indigo-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-indigo-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-100 text-indigo-700"><Gauge className="h-5 w-5" /></span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电气缸设备异常检测智能体</h3>
              <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[9px] font-medium text-indigo-700"><Activity className="h-3 w-3" />异常检测</span>
            </div>
          </div>
          <p className="relative mt-4 text-xs leading-5 text-steel-500">监测气缸压力、位移、速度和运行节拍等关键特征，定位异常时段与潜在故障。</p>
          <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-indigo-700">配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
        </button>
        <button
          type="button"
          onClick={onOpenServoMotorAnomalyAgent}
          className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-sky-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-sky-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-sky-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-100 text-sky-700"><Disc3 className="h-5 w-5" /></span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电伺服电机异常检测智能体</h3>
              <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[9px] font-medium text-sky-700"><Activity className="h-3 w-3" />异常检测</span>
            </div>
          </div>
          <p className="relative mt-4 text-xs leading-5 text-steel-500">监测伺服电机电流、扭矩、转速和位置误差等关键特征，定位运行异常与潜在故障。</p>
          <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-sky-700">配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
        </button>
        <button
          type="button"
          onClick={onOpenWeldingAnomalyAgent}
          className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-orange-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-orange-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-orange-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-100 text-orange-700"><Flame className="h-5 w-5" /></span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电焊接设备异常检测智能体</h3>
              <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-orange-200 bg-orange-50 px-2 py-0.5 text-[9px] font-medium text-orange-700"><Activity className="h-3 w-3" />异常检测</span>
            </div>
          </div>
          <p className="relative mt-4 text-xs leading-5 text-steel-500">监测焊接功率、速度、焦点和熔池温度等关键特征，定位设备异常与潜在焊接缺陷。</p>
          <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-orange-700">配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
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
  onOpenRawMaterialPriceForecastAgent,
}: {
  onOpenBatteryAgent: () => void;
  onOpenVehicleSalesAgent: () => void;
  onOpenRawMaterialPriceForecastAgent: () => void;
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
        <button
          type="button"
          onClick={onOpenRawMaterialPriceForecastAgent}
          className="group relative flex min-h-[180px] flex-col overflow-hidden rounded-2xl border border-orange-200/80 bg-white p-4 text-left shadow-sm transition-all hover:border-orange-400 hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2"
        >
          <span aria-hidden="true" className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-orange-50 opacity-70 transition-transform duration-300 group-hover:scale-110" />
          <div className="relative flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-100 text-orange-700">
              <Coins className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[13px] font-semibold leading-5 text-steel-800">锂电原材料价格预测智能体</h3>
              <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-orange-200 bg-orange-50 px-2 py-0.5 text-[9px] font-medium text-orange-700">
                <ChartSpline className="h-3 w-3" />时序预测
              </span>
            </div>
          </div>
          <p className="relative mt-4 text-xs leading-5 text-steel-500">
            结合历史价格与供需、库存和下游需求数据，预测锂电原材料价格走势。
          </p>
          <span className="relative mt-auto flex items-center justify-end gap-1 pt-3 text-[11px] font-medium text-orange-700">
            配置任务<ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </span>
        </button>
      </div>
    </div>
  );
}
