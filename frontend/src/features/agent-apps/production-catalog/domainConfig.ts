import { Activity, BatteryCharging, BatteryMedium, BatteryWarning, Boxes, CarFront, Coins, Disc3, Factory, Flame, Gauge, Store, Wrench, Zap, type LucideIcon } from 'lucide-react';
import { PRODUCTION_GROUPS, type ProductionGroupId } from './config';
import { PRODUCTION_BI_AGENTS } from '../production-bi-analysis/config';
import { NG_DEFECT_AGENT } from '../ng-defect-analysis/config';
import { CELL_PRODUCTION_FORECAST_AGENT } from '../cell-production-forecast/config';
import { PACK_PRODUCTION_FORECAST_AGENT } from '../pack-production-forecast/config';
import { FACTORY_ENERGY_FORECAST_AGENT } from '../factory-energy-forecast/config';
import { COATING_AREAL_DENSITY_AGENT } from '../coating-areal-density-analysis/config';
import { COATING_AREAL_DENSITY_ANOMALY_AGENT } from '../coating-areal-density-anomaly-detection/config';
import { CELL_CAPACITY_ROOT_CAUSE_AGENT } from '../cell-capacity-root-cause/config';
import { CYLINDER_EQUIPMENT_ANOMALY_AGENT } from '../cylinder-equipment-anomaly-detection/config';
import { SERVO_MOTOR_ANOMALY_AGENT } from '../servo-motor-anomaly-detection/config';
import { WELDING_EQUIPMENT_ANOMALY_AGENT } from '../welding-equipment-anomaly-detection/config';
import { BATTERY_INSTALLATION_AGENT } from '../battery-installation-forecast/config';
import { VEHICLE_SALES_AGENTS } from '../new-energy-vehicle-sales/config';
import { RAW_MATERIAL_PRICE_FORECAST_AGENT } from '../raw-material-price-forecast/config';
import { CELL_SOH_FORECAST_AGENT } from '../cell-soh-forecast/config';

export type AgentDomain = 'equipment' | 'production' | 'market';
export const DOMAIN_META: Record<AgentDomain, { title: string; description: string; icon: LucideIcon }> = {
 equipment: { title: '设备域', description: '连接设备现场与智能能力，探索运行状态背后的更多可能。', icon: Wrench },
 production: { title: '生产域', description: '汇聚生产现场的智能能力，连接通用场景与工厂空间。', icon: Factory },
 market: { title: '市场域', description: '连接市场变化与业务判断，探索数据中的发展机遇。', icon: Store },
};
export interface CatalogAgent { id: string; name: string; description: string; icon: LucideIcon; tag: string; }
const equipment: CatalogAgent[] = [
 {...COATING_AREAL_DENSITY_AGENT, icon: Activity, tag: '时序分析'},
 {...COATING_AREAL_DENSITY_ANOMALY_AGENT, icon: Gauge, tag: '异常检测'},
 {...CELL_CAPACITY_ROOT_CAUSE_AGENT, icon: BatteryWarning, tag: '根因分析'},
 {...CYLINDER_EQUIPMENT_ANOMALY_AGENT, icon: Gauge, tag: '异常检测'},
 {...SERVO_MOTOR_ANOMALY_AGENT, icon: Disc3, tag: '异常检测'},
 {...WELDING_EQUIPMENT_ANOMALY_AGENT, icon: Flame, tag: '异常检测'},
];
const market: CatalogAgent[] = [
 {...BATTERY_INSTALLATION_AGENT, icon: BatteryCharging, tag: '时序预测'},
 ...VEHICLE_SALES_AGENTS.map(agent => ({...agent, icon: CarFront, tag: '销量预测'})),
 {...RAW_MATERIAL_PRICE_FORECAST_AGENT, icon: Coins, tag: '价格预测'},
 {...CELL_SOH_FORECAST_AGENT, icon: BatteryMedium, tag: '寿命预测'},
];
const production: CatalogAgent[] = [
 {...CELL_PRODUCTION_FORECAST_AGENT, icon: BatteryMedium, tag: '产量预测'},
 {...PACK_PRODUCTION_FORECAST_AGENT, icon: Boxes, tag: '产量预测'},
 {...FACTORY_ENERGY_FORECAST_AGENT, icon: Zap, tag: '能耗预测'},
 ...PRODUCTION_BI_AGENTS.map(agent => ({...agent, tag: 'BI 分析'})),
 {...NG_DEFECT_AGENT, tag: 'NG 问数'},
];
export const CATALOG_AGENTS = new Map<string, CatalogAgent>([...equipment, ...production, ...market].map(agent => [agent.id, agent]));
export interface CatalogGroup { tenantId?: string; id: ProductionGroupId; title: string; subtitle: string; description: string; agents: readonly string[]; }
export function getDomainGroups(domain: AgentDomain): CatalogGroup[] {
 if (domain === 'production') return [...PRODUCTION_GROUPS];
 return PRODUCTION_GROUPS.map(group => ({ ...group, agents: group.id === 'general' ? (domain === 'equipment' ? equipment : market).map(agent => agent.id) : [] }));
}
export function getGroupAgents(domain: AgentDomain, groupId: ProductionGroupId): CatalogAgent[] {
 return (getDomainGroups(domain).find(group => group.id === groupId)?.agents ?? []).map(id => CATALOG_AGENTS.get(id)).filter((agent): agent is CatalogAgent => Boolean(agent));
}
