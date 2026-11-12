import { CONTROL_PLAN_AGENT } from '../control-plan-analysis/config';
import { CELL_PRODUCTION_FORECAST_AGENT } from '../cell-production-forecast/config';
import { PACK_PRODUCTION_FORECAST_AGENT } from '../pack-production-forecast/config';
import { FACTORY_ENERGY_FORECAST_AGENT } from '../factory-energy-forecast/config';
import { PRODUCTION_BI_AGENTS } from '../production-bi-analysis/config';
import { NG_DEFECT_AGENT } from '../ng-defect-analysis/config';

export const PRODUCTION_GROUPS = [
  { id: 'general', title: '通用智能体', subtitle: '跨工厂的通用能力', description: '汇聚可复用的智能能力，连接不同场景与工厂。', agents: [CELL_PRODUCTION_FORECAST_AGENT.id, PACK_PRODUCTION_FORECAST_AGENT.id, FACTORY_ENERGY_FORECAST_AGENT.id, CONTROL_PLAN_AGENT.id] },
  { id: 'jinzhai-phase-2', tenantId: '11200001', title: '金寨二期工厂智能体', subtitle: '工厂专属空间', description: '连接工厂业务与智能能力，探索现场的更多可能。', agents: [...PRODUCTION_BI_AGENTS.map(agent => agent.id), NG_DEFECT_AGENT.id] },
  { id: 'jinzhai-phase-3', tenantId: '11300001', title: '金寨三期工厂智能体', subtitle: '工厂专属空间', description: '让智能能力融入业务，持续拓展工厂应用场景。', agents: [...PRODUCTION_BI_AGENTS.map(agent => agent.id), NG_DEFECT_AGENT.id] },
  { id: 'wuhu-phase-1', tenantId: '14100001', title: '芜湖一期工厂智能体', subtitle: '工厂专属空间', description: '连接现场，探索更多可能。', agents: [...PRODUCTION_BI_AGENTS.map(agent => agent.id), NG_DEFECT_AGENT.id] },
  { id: 'xinzhan-phase-2', title: '新站二期工厂智能体', subtitle: '工厂专属空间', description: '连接现场，探索更多可能。', agents: [] },
] as const;
export type ProductionGroupId = typeof PRODUCTION_GROUPS[number]['id'];
export const PRODUCTION_AGENT_COUNT = PRODUCTION_GROUPS.reduce((total, group) => total + group.agents.length, 0);
