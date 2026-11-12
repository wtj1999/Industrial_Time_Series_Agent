import { ControlPlanAnalysisApp } from '@/features/agent-apps/control-plan-analysis/ControlPlanAnalysisApp';
import { CONTROL_PLAN_AGENT } from '@/features/agent-apps/control-plan-analysis/config';
import { useState } from 'react';
import { ArrowLeft, Bot } from 'lucide-react';
import { useSession } from '@/context/SessionContext';
import { BatteryInstallationForecastApp } from '@/features/agent-apps/battery-installation-forecast/BatteryInstallationForecastApp';
import { BATTERY_INSTALLATION_AGENT } from '@/features/agent-apps/battery-installation-forecast/config';
import { NewEnergyVehicleSalesApp } from '@/features/agent-apps/new-energy-vehicle-sales/NewEnergyVehicleSalesApp';
import { VEHICLE_SALES_AGENTS } from '@/features/agent-apps/new-energy-vehicle-sales/config';
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
import { CellSohForecastApp } from '@/features/agent-apps/cell-soh-forecast/CellSohForecastApp';
import { CELL_SOH_FORECAST_AGENT } from '@/features/agent-apps/cell-soh-forecast/config';
import { ProductionBiAnalysisApp } from '@/features/agent-apps/production-bi-analysis/ProductionBiAnalysisApp';
import { PRODUCTION_BI_AGENTS, type ProductionBiAgent } from '@/features/agent-apps/production-bi-analysis/config';
import { NG_DEFECT_AGENT } from '@/features/agent-apps/ng-defect-analysis/config';

import { ProductionCatalog, DomainCatalog } from '@/features/agent-apps/production-catalog/ProductionCatalog';
import type { ProductionGroupId } from '@/features/agent-apps/production-catalog/config';
import { DOMAIN_META, CATALOG_AGENTS, getDomainGroups, type AgentDomain } from '@/features/agent-apps/production-catalog/domainConfig';

const PRODUCTION_QUERY_AGENTS: readonly ProductionBiAgent[] = [...PRODUCTION_BI_AGENTS, NG_DEFECT_AGENT, CONTROL_PLAN_AGENT];

export function MyAgentsView({ onBack }: { onBack: () => void }) {
  const { initNewSession } = useSession();
  const [activeDomain, setActiveDomain] = useState<AgentDomain | null>(null);
  const [activeGroup, setActiveGroup] = useState<ProductionGroupId | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const groups = activeDomain ? getDomainGroups(activeDomain) : [];
  const groupMeta = groups.find(group => group.id === activeGroup);
  const activeMeta = activeDomain ? DOMAIN_META[activeDomain] : null;
  const activeAgentName = activeAgent ? CATALOG_AGENTS.get(activeAgent)?.name : '';
  const activeBiAgent = PRODUCTION_QUERY_AGENTS.find(agent => agent.id === activeAgent);
  const activeVehicleSalesAgent = VEHICLE_SALES_AGENTS.find(agent => agent.id === activeAgent);

  const handleBack = () => {
    if (activeAgent) setActiveAgent(null);
    else if (activeGroup) setActiveGroup(null);
    else if (activeDomain) setActiveDomain(null);
    else onBack();
  };
  const openAgent = (agentId: string) => {
    if (!CATALOG_AGENTS.has(agentId)) return;
    if (!PRODUCTION_QUERY_AGENTS.some(agent => agent.id === agentId)) initNewSession();
    setActiveAgent(agentId);
  };
  const renderAgent = () => {
    if (activeAgent === CONTROL_PLAN_AGENT.id) return <ControlPlanAnalysisApp />;
    if (activeBiAgent) return <ProductionBiAnalysisApp key={`${activeGroup}:${activeBiAgent.id}`} agent={{ ...activeBiAgent, ...(activeBiAgent.analysisDomain && groupMeta?.tenantId ? { tenantId: groupMeta.tenantId } : {}), ...(activeBiAgent.id === NG_DEFECT_AGENT.id && activeGroup ? { ngFactoryId: activeGroup } : {}) }} />;
    if (activeVehicleSalesAgent) return <NewEnergyVehicleSalesApp key={activeVehicleSalesAgent.id} agent={activeVehicleSalesAgent} />;
    switch (activeAgent) {
      case BATTERY_INSTALLATION_AGENT.id: return <BatteryInstallationForecastApp />;
      case RAW_MATERIAL_PRICE_FORECAST_AGENT.id: return <RawMaterialPriceForecastApp />;
      case CELL_SOH_FORECAST_AGENT.id: return <CellSohForecastApp />;
      case COATING_AREAL_DENSITY_AGENT.id: return <CoatingArealDensityAnalysisApp />;
      case COATING_AREAL_DENSITY_ANOMALY_AGENT.id: return <CoatingArealDensityAnomalyDetectionApp />;
      case CYLINDER_EQUIPMENT_ANOMALY_AGENT.id: return <CylinderEquipmentAnomalyDetectionApp />;
      case SERVO_MOTOR_ANOMALY_AGENT.id: return <ServoMotorAnomalyDetectionApp />;
      case WELDING_EQUIPMENT_ANOMALY_AGENT.id: return <WeldingEquipmentAnomalyDetectionApp />;
      case CELL_CAPACITY_ROOT_CAUSE_AGENT.id: return <CellCapacityRootCauseApp />;
      case CELL_PRODUCTION_FORECAST_AGENT.id: return <CellProductionForecastApp />;
      case PACK_PRODUCTION_FORECAST_AGENT.id: return <PackProductionForecastApp />;
      case FACTORY_ENERGY_FORECAST_AGENT.id: return <FactoryEnergyForecastApp />;
      default: return null;
    }
  };

  return <div className={`flex h-full flex-col catalog-theme-${activeDomain ?? 'production'}`}>
    <div className="flex items-center gap-3 border-b border-steel-200/70 bg-white/60 px-4 py-3 backdrop-blur-md sm:px-6">
      <button type="button" onClick={handleBack}
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-steel-600 transition-colors hover:bg-steel-100 hover:text-steel-900"
        title={activeAgent ? `返回${groupMeta?.title ?? activeMeta?.title ?? '智能体列表'}` : activeGroup ? `返回${activeMeta?.title}` : activeDomain ? '返回智能体分类' : '返回对话'}>
        <ArrowLeft className="h-4 w-4" />
      </button>
      <div className="flex min-w-0 items-center gap-2">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg catalog-header-icon"><Bot className="h-3.5 w-3.5" /></span>
        <h1 className="text-sm font-semibold text-steel-800">{activeAgent ? activeAgentName : groupMeta?.title ?? activeMeta?.title ?? '我的智能体'}</h1>
        {!activeAgent && <span className="shrink-0 rounded-full bg-steel-100 px-2 py-0.5 text-[10px] font-medium text-steel-600">
          {groupMeta ? `${groupMeta.agents.length} 个智能体` : activeDomain ? `${groups.length} 个分类` : '3 个领域'}
        </span>}
      </div>
      {activeDomain && <nav className="production-breadcrumb ml-auto" aria-label={`${activeMeta?.title}导航`}>
        <button type="button" onClick={() => { setActiveAgent(null); setActiveGroup(null); setActiveDomain(null); }}>业务领域</button><span>/</span>
        <button type="button" onClick={() => { setActiveAgent(null); setActiveGroup(null); }}>{activeMeta?.title}</button>
        {groupMeta && <><span>/</span><button type="button" onClick={() => setActiveAgent(null)}>{groupMeta.title}</button></>}
        {activeAgent && <><span>/</span><span aria-current="page">{activeAgentName}</span></>}
      </nav>}
    </div>
    {activeAgent ? renderAgent() : <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6"><div className="mx-auto w-full max-w-5xl">
      {activeDomain ? <ProductionCatalog domain={activeDomain} groupId={activeGroup} onSelectGroup={setActiveGroup} onOpenAgent={openAgent} /> : <DomainCatalog onSelect={setActiveDomain} />}
    </div></div>}
  </div>;
}
