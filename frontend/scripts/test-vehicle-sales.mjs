import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const compile = (source) => `data:text/javascript;base64,${Buffer.from(ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
}).outputText).toString('base64')}`;
const baseConfig = compile(await readFile(new URL('../src/features/agent-apps/battery-installation-forecast/config.ts', import.meta.url), 'utf8'));
const source = (await readFile(new URL('../src/features/agent-apps/new-energy-vehicle-sales/config.ts', import.meta.url), 'utf8'))
  .replace('@/features/agent-apps/battery-installation-forecast/config', baseConfig);
const { BRAND_VEHICLE_SALES_AGENTS, VEHICLE_SALES_AGENTS, buildVehicleSalesForecastQuery } = await import(compile(source));
const task = { model: 'chronos-2', granularity: '季度', horizon: 4, vehicleSegments: ['BEV', '乘用车'],
  externalVariables: ['汽车出口量'], additionalRequirements: '重点分析季度波动。' };

assert.deepEqual(BRAND_VEHICLE_SALES_AGENTS.map(({ id, brand }) => [id, brand]), [
  ['leapmotor-sales-forecast', '零跑汽车'], ['geely-sales-forecast', '吉利汽车'], ['great-wall-sales-forecast', '长城汽车'],
]);
assert.equal(VEHICLE_SALES_AGENTS.length, 4);
assert.equal(new Set(VEHICLE_SALES_AGENTS.map((agent) => agent.id)).size, 4);
for (const agent of BRAND_VEHICLE_SALES_AGENTS) {
  assert.ok(agent.vehicleModels.length >= 3);
  assert.ok(!agent.vehicleModels.some((value) => ['BEV', 'PHEV', 'EREV', '乘用车', '商用车'].includes(value)));
  const selectedModels = agent.vehicleModels.slice(0, 2);
  const query = buildVehicleSalesForecastQuery({ ...task, vehicleSegments: selectedModels }, agent);
  assert.ok(query.includes(`预测目标：${agent.brand}销量；指定预测模型：chronos-2；时间粒度：季度。`));
  assert.ok(query.includes(`品牌范围：仅分析${agent.brand}销量`));
  assert.ok(query.includes('不能以全行业销量或其他品牌销量代替'));
  assert.ok(query.includes('预测未来 4 个季度。'));
  assert.ok(query.includes(`车型型号：${selectedModels.join('、')}。`));
  assert.ok(!query.includes('BEV'));
  assert.ok(query.includes('可参考的外生变量：汽车出口量。'));
  assert.ok(query.includes('补充要求：重点分析季度波动。'));
  assert.ok(!query.includes('预测目标：新能源汽车销量'));
  const defaultQuery = buildVehicleSalesForecastQuery({ ...task, model: 'sundial', granularity: '月度', horizon: 6,
    vehicleSegments: [], externalVariables: [], additionalRequirements: '  ' }, agent);
  assert.ok(defaultQuery.includes('车型型号：全部车型。'));
  assert.ok(defaultQuery.includes('预测未来 6 个月。'));
  assert.ok(defaultQuery.includes('输出点预测、置信区间'));
}
const generic = buildVehicleSalesForecastQuery(task);
assert.ok(generic.startsWith('请执行新能源汽车销量时间序列预测任务。'));
assert.ok(!generic.includes('品牌范围'));
console.log('Vehicle sales checks passed: distinct brand IDs, scoped targets, parameter forwarding and original application defaults.');
