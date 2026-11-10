import { ArrowRight, Factory, FolderOpen, Layers3 } from 'lucide-react';
import type { ProductionGroupId } from './config';
import { DOMAIN_META, getDomainGroups, getGroupAgents, type AgentDomain } from './domainConfig';
import { CatalogCard } from './CatalogCard';
import { DirectoryArtwork } from './DirectoryArtwork';
import './ProductionCatalog.css';

export function ProductionCatalog({ domain = 'production', groupId, onSelectGroup, onOpenAgent }: {
  domain?: AgentDomain;
  groupId: ProductionGroupId | null;
  onSelectGroup: (id: ProductionGroupId | null) => void;
  onOpenAgent: (id: string) => void;
}) {
  const groups = getDomainGroups(domain);
  const meta = DOMAIN_META[domain];
  const group = groups.find(item => item.id === groupId);
  if (group) {
    const agents = getGroupAgents(domain, group.id);
    return <section className={`production-catalog production-group-detail catalog-theme-${domain}`} aria-label={group.title}>
      <div className="production-directory-heading"><div><span className="production-eyebrow">{meta.title} · {group.subtitle}</span><h2>{group.title}</h2><p>{group.agents.length ? group.description : '当前分类下暂未配置智能体。'}</p></div><span className="production-directory-count">{group.agents.length} 个智能体</span></div>
      {agents.length ? <div className="catalog-grid catalog-grid-agents" data-count={agents.length}>{agents.map((agent, index) => <CatalogCard
        key={agent.id} title={agent.name} description={agent.description} icon={agent.icon} index={index} kind={agent.tag}
        className={`catalog-entry ${index === 0 ? 'catalog-tone-dark' : index === 2 ? 'catalog-tone-soft' : ''}`}
        action={agent.tag.endsWith('预测') || agent.tag === '异常检测' || agent.tag === '时序分析' || agent.tag === '根因分析' ? '配置任务' : '进入智能体'}
        onClick={() => onOpenAgent(agent.id)}
      />)}</div> : <div className="production-empty"><span><FolderOpen size={36} strokeWidth={1.2}/></span><h3>暂无智能体</h3><p>你可以返回{meta.title}，查看通用能力或其他工厂目录。</p><button type="button" onClick={() => onSelectGroup(null)}>返回{meta.title}<ArrowRight size={15}/></button></div>}
    </section>;
  }
  return <section className={`production-catalog catalog-theme-${domain}`} aria-label={`${meta.title}分类目录`}>
    <div className="production-directory-heading"><div><span className="production-eyebrow"><Layers3 size={13}/> {meta.title} · 能力目录</span><h2>通用能力，与工厂现场相连<span>。</span></h2><p>选择通用能力，或进入工厂的专属智能空间。</p></div><div className="production-directory-overview"><strong>{String(groups.length).padStart(2, '0')}<span>个分类</span></strong></div></div>
    <div className="production-directory-grid">
      {groups.map((item, index) => <CatalogCard key={item.id} title={item.title} description={item.description} subtitle={item.subtitle}
        icon={item.id === 'general' ? Layers3 : Factory} index={index} kind={item.id === 'general' ? '通用能力' : '工厂空间'}
        className={`production-card-${item.id}`} onClick={() => onSelectGroup(item.id)}>
        <DirectoryArtwork domain={domain} groupId={item.id} />
      </CatalogCard>)}
    </div>
  </section>;
}

export function DomainCatalog({ onSelect }: { onSelect: (domain: AgentDomain) => void }) {
 return <section className="production-catalog catalog-theme-production" aria-label="业务领域目录">
  <div className="production-directory-heading"><div><span className="production-eyebrow"><Layers3 size={13}/>智能体 · 业务领域</span><h2>让智能，走进业务现场<span>。</span></h2><p>从领域出发，探索通用能力与工厂专属空间。</p></div><span className="production-directory-count">3 个领域</span></div>
  <div className="catalog-grid catalog-grid-domains">{(Object.keys(DOMAIN_META) as AgentDomain[]).map((domain,index) => {
    const meta=DOMAIN_META[domain];
    return <CatalogCard key={domain} title={meta.title} description={meta.description} icon={meta.icon} index={index} kind="业务领域"
      className={`catalog-entry catalog-theme-${domain} ${index===0?'catalog-tone-dark':'catalog-tone-soft'}`} onClick={()=>onSelect(domain)} />;
  })}</div>
 </section>;
}
