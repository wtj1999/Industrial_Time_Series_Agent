import { useEffect, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from 'react';
import { Activity, ArrowLeft, ArrowRight, BatteryCharging, BarChart3, Boxes, ChartSpline, Disc3, Factory, Gauge, LineChart, ScanSearch, Store, Wrench, Zap, type LucideIcon } from 'lucide-react';

type Domain = 'equipment' | 'production' | 'market';
type Agent = { name: string; description: string; capability: string; icon: LucideIcon; tone: string };

const DOMAINS: Record<Domain, { title: string; description: string; icon: LucideIcon; code: string; label: string; signal: number[]; features: [string, string] }> = {
  equipment: { title: '设备域', description: '状态监测、异常检测与根因分析', icon: Wrench, code: '01', label: 'ASSET INTELLIGENCE', signal: [8, 13, 10, 18, 12, 20, 13, 17], features: ['实时监测', '故障溯源'] },
  production: { title: '生产域', description: '产量、能耗与生产经营分析', icon: Factory, code: '02', label: 'PRODUCTION INSIGHT', signal: [7, 10, 13, 11, 15, 17, 20, 18], features: ['产能推演', '能效洞察'] },
  market: { title: '市场域', description: '销量、装车量与价格趋势预测', icon: Store, code: '03', label: 'MARKET FORESIGHT', signal: [13, 8, 11, 7, 13, 10, 17, 20], features: ['趋势预测', '需求洞察'] },
};
const DOMAIN_ORDER: Domain[] = ['equipment', 'production', 'market'];
const AGENTS: Record<Domain, Agent[]> = {
  equipment: [
    { name: '锂电涂布面密度分析智能体', description: '分析面密度稳定性、过程能力、漂移、变点与分区关联。', capability: '过程分析', icon: BarChart3, tone: 'violet' },
    { name: '锂电涂布面密度异常检测智能体', description: '检测异常时间点、连续异常区间及主要异常分区。', capability: '异常检测', icon: ScanSearch, tone: 'cyan' },
    { name: '锂电气缸设备异常检测智能体', description: '监测压力、位移、速度和运行节拍，定位异常与潜在故障。', capability: '状态监测', icon: Gauge, tone: 'indigo' },
    { name: '锂电伺服电机异常检测智能体', description: '监测电流、扭矩、转速和位置误差等关键运行特征。', capability: '异常检测', icon: Disc3, tone: 'sky' },
  ],
  production: [
    { name: '锂电电芯产量预测智能体', description: '结合历史产量、产线运行与质量数据预测产量及产能缺口。', capability: '产量预测', icon: ChartSpline, tone: 'emerald' },
    { name: '锂电PACK产量预测智能体', description: '结合电芯齐套、PACK产线运行与质量数据预测未来产量。', capability: '产能规划', icon: Boxes, tone: 'teal' },
    { name: '锂电工厂能耗预测智能体', description: '预测工厂未来能耗及单位产量能耗变化。', capability: '能耗预测', icon: Zap, tone: 'amber' },
    { name: '生产BI分析智能体', description: '围绕生产经营数据进行多维指标分析与业务洞察。', capability: '经营分析', icon: BarChart3, tone: 'blue' },
  ],
  market: [
    { name: '动力电池装车量预测智能体', description: '基于历史装车量与市场数据预测未来动力电池装车量。', capability: '装车量预测', icon: BatteryCharging, tone: 'cyan' },
    { name: '新能源汽车销量预测智能体', description: '预测新能源汽车未来销量及细分市场趋势。', capability: '销量预测', icon: LineChart, tone: 'blue' },
    { name: '锂电原材料价格预测智能体', description: '结合供需、库存和下游需求数据预测原材料价格走势。', capability: '价格预测', icon: ChartSpline, tone: 'amber' },
    { name: '锂电电芯SOH预测智能体', description: '根据容量衰减序列预测电芯达到目标 SOH 的循环圈数。', capability: '寿命预测', icon: Activity, tone: 'emerald' },
  ],
};


function AgentTiltCard({ agent, index, onLogin }: { agent: Agent; index: number; onLogin: () => void }) {
  const cardRef = useRef<HTMLButtonElement>(null);
  const frameRef = useRef<number | null>(null);
  useEffect(() => () => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
  }, []);

  const resetTilt = () => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    const card = cardRef.current;
    if (!card) return;
    card.dataset.tilting = 'false';
    card.style.setProperty('--agent-rx', '0deg');
    card.style.setProperty('--agent-ry', '0deg');
    card.style.setProperty('--agent-mx', '50%');
    card.style.setProperty('--agent-my', '50%');
    card.style.setProperty('--agent-shadow-x', '0px');
  };

  const followPointer = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.pointerType === 'touch' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const card = event.currentTarget;
    const bounds = card.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(() => {
      card.dataset.tilting = 'true';
      card.style.setProperty('--agent-rx', `${((.5 - y) * 3).toFixed(2)}deg`);
      card.style.setProperty('--agent-ry', `${((x - .5) * 4).toFixed(2)}deg`);
      card.style.setProperty('--agent-mx', `${(x * 100).toFixed(1)}%`);
      card.style.setProperty('--agent-my', `${(y * 100).toFixed(1)}%`);
    });
  };

  const Icon = agent.icon;
  return <button ref={cardRef} type="button" style={{ '--agent-index': index } as CSSProperties} className={`auth-agent-card auth-agent-${agent.tone}`} onPointerMove={followPointer} onPointerLeave={resetTilt} onPointerCancel={resetTilt} onBlur={resetTilt} onClick={onLogin}>
    <span className="auth-agent-orb" aria-hidden="true"/>
    <span className="auth-agent-glint" aria-hidden="true"/>
    <span className="auth-agent-card-top"><span className="auth-agent-icon"><Icon size={20} strokeWidth={1.6}/></span><span className="auth-agent-tag">{agent.capability}</span></span>
    <strong>{agent.name}</strong><p>{agent.description}</p>
    <span className="auth-agent-action">登录后配置任务 <ArrowRight size={14}/></span>
  </button>;
}

export function AuthShowcase({ onLogin }: { onLogin: () => void }) {
  const [domain, setDomain] = useState<Domain>('equipment');
  const [carouselPaused, setCarouselPaused] = useState(false);
  const resumeTimerRef = useRef<number>();
  const manualPauseUntilRef = useRef(0);
  const meta = DOMAINS[domain];

  useEffect(() => {
    if (carouselPaused || document.hidden || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const timer = window.setInterval(() => {
      if (document.hidden || Date.now() < manualPauseUntilRef.current) return;
      setDomain(current => DOMAIN_ORDER[(DOMAIN_ORDER.indexOf(current) + 1) % DOMAIN_ORDER.length]);
    }, 4200);
    return () => window.clearInterval(timer);
  }, [carouselPaused]);

  useEffect(() => () => window.clearTimeout(resumeTimerRef.current), []);

  const selectDomain = (next: Domain) => {
    manualPauseUntilRef.current = Date.now() + 6500;
    setDomain(next);
    setCarouselPaused(true);
    window.clearTimeout(resumeTimerRef.current);
    resumeTimerRef.current = window.setTimeout(() => setCarouselPaused(false), 6500);
  };
  const selectFromCarousel = (event: ReactPointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const position = (event.clientX - bounds.left) / bounds.width;
    const activeIndex = DOMAIN_ORDER.indexOf(domain);
    if (position < .32) selectDomain(DOMAIN_ORDER[(activeIndex + 2) % DOMAIN_ORDER.length]);
    if (position > .68) selectDomain(DOMAIN_ORDER[(activeIndex + 1) % DOMAIN_ORDER.length]);
  };
  return <section className="auth-agents-section" id="agent-scenes" aria-labelledby="auth-agents-heading">
    <div className="auth-agents-heading"><div><p>真实应用场景</p><h2 id="auth-agents-heading">面向工业业务的专业智能体</h2><span>选择业务领域，探索平台已有的专业智能体。</span></div></div>
    <div className="auth-domain-layout">
      <div className="auth-domain-carousel-shell">
      <button className="auth-carousel-control is-prev" type="button" aria-label="上一个领域" onClick={() => selectDomain(DOMAIN_ORDER[(DOMAIN_ORDER.indexOf(domain) + 2) % DOMAIN_ORDER.length])}><ArrowLeft size={17}/></button>
      <div className="auth-domain-tabs auth-domain-carousel" onPointerDownCapture={selectFromCarousel} onMouseEnter={() => setCarouselPaused(true)} onMouseLeave={() => setCarouselPaused(false)} onFocusCapture={() => setCarouselPaused(true)} onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget)) setCarouselPaused(false); }} role="tablist" aria-label="智能体领域">{DOMAIN_ORDER.map(key => { const item=DOMAINS[key]; const Icon=item.icon; const offset=(DOMAIN_ORDER.indexOf(key)-DOMAIN_ORDER.indexOf(domain)+3)%3; const position=offset===0?'is-front':offset===1?'is-right':'is-left'; return <button className={`${position} auth-domain-${key}`} key={key} type="button" role="tab" aria-selected={domain===key} aria-controls="auth-agent-panel" onClick={() => selectDomain(key)}><span className="auth-domain-shine" aria-hidden="true"/><span className="auth-domain-kicker"><em>{item.code}</em>{item.label}</span><span className="auth-domain-icon"><Icon size={21} strokeWidth={1.45}/></span><span className="auth-domain-copy"><strong>{item.title}</strong><small>{item.description}</small><span className="auth-domain-features">{item.features.map(feature => <i key={feature}>{feature}</i>)}</span></span><span className="auth-domain-signal" aria-hidden="true">{item.signal.map((height,index)=><i key={index} style={{height}} />)}</span><span className="auth-domain-rail" aria-hidden="true"/></button>; })}</div>
      <button className="auth-carousel-control is-next" type="button" aria-label="下一个领域" onClick={() => selectDomain(DOMAIN_ORDER[(DOMAIN_ORDER.indexOf(domain) + 1) % DOMAIN_ORDER.length])}><ArrowRight size={17}/></button>
      <div className="auth-carousel-dots" aria-label="领域轮播分页">{DOMAIN_ORDER.map((key,index) => <button key={key} type="button" aria-label={`切换到第 ${index + 1} 页：${DOMAINS[key].title}`} aria-current={domain === key ? 'true' : undefined} onClick={() => selectDomain(key)} />)}</div>
      </div>
      <div className="auth-agent-panel" id="auth-agent-panel" role="tabpanel" aria-live="polite"><div className="auth-agent-panel-head"><div><strong>{meta.title}智能体</strong><span>{meta.description}</span></div></div><div className="auth-agent-grid" key={domain}>{AGENTS[domain].map((agent,index) => <AgentTiltCard key={agent.name} agent={agent} index={index} onLogin={onLogin} />)}</div></div>
    </div>
  </section>;
}
