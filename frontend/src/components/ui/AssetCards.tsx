import type { LucideIcon } from 'lucide-react';
import { CatalogCard } from '@/features/agent-apps/production-catalog/CatalogCard';
import '@/features/agent-apps/production-catalog/ProductionCatalog.css';
import './AssetCards.css';

export type AssetMotif = 'online' | 'offline' | 'data_analysis' | 'anomaly_detection' | 'time_series_prediction' | 'table';

export function assetTheme(motif: AssetMotif) {
  if (motif === 'offline' || motif === 'data_analysis') return 'catalog-theme-production';
  if (motif === 'anomaly_detection') return 'catalog-theme-equipment catalog-theme-models';
  return 'catalog-theme-equipment';
}

export function AssetArtwork({ motif }: { motif: AssetMotif }) {
  return <svg className="asset-artwork" viewBox="0 0 240 150" fill="none" stroke="currentColor" strokeWidth="1.2"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {motif === 'online' ? <>
      <ellipse cx="163" cy="44" rx="43" ry="16"/><path d="M120 44V104C120 125 206 125 206 104V44M120 73C120 94 206 94 206 73"/>
      <path d="M23 78H66L89 55H120M38 118H77L104 92H120M73 27H101L120 44"/>
      <g fill="currentColor" stroke="none"><circle cx="23" cy="78" r="4"/><circle cx="38" cy="118" r="4"/><circle cx="73" cy="27" r="4"/></g>
      <path d="M218 54V95M229 65V84" opacity=".5"/>
    </> : motif === 'offline' ? <>
      <path d="M80 24H159L183 48V126H80ZM159 24V48H183M97 65H165M97 81H165M97 97H143"/>
      <path d="M63 38H52V137H158V126M36 55H26V145H129" opacity=".5"/>
      <path d="M196 84H222V121H196M204 104L209 109 216 98"/>
    </> : motif === 'data_analysis' ? <>
      <path d="M34 115L85 84 137 106 197 39M85 84L113 35M137 106L204 127"/>
      <g fill="currentColor" fillOpacity=".06"><circle cx="34" cy="115" r="10"/><circle cx="85" cy="84" r="16"/><circle cx="137" cy="106" r="11"/><circle cx="197" cy="39" r="15"/><circle cx="113" cy="35" r="8"/><circle cx="204" cy="127" r="8"/></g>
      <path d="M22 135H216M22 18V135" opacity=".25"/>
    </> : motif === 'anomaly_detection' ? <>
      <path d="M18 44H222M18 80H222M18 116H222" opacity=".25" strokeDasharray="2 6"/>
      <path d="M17 95L41 93 57 80 73 97 91 91 110 94 130 33 148 119 165 88 181 96 202 87 223 92" strokeWidth="1.8"/>
      <circle cx="130" cy="33" r="13"/><circle cx="130" cy="33" r="23" opacity=".4"/>
      <path d="M130 61V129" strokeDasharray="3 5"/>
    </> : motif === 'time_series_prediction' ? <>
      <path d="M16 125H225M16 25V125" opacity=".35"/>
      <path d="M135 72L160 57 183 67 219 32V71L183 104 160 94 135 106Z" fill="currentColor" fillOpacity=".08" stroke="none"/>
      <path d="M22 111L46 99 69 106 91 80 113 89 135 90" strokeWidth="1.8"/>
      <path d="M135 90L160 75 183 85 219 50" strokeWidth="1.8" strokeDasharray="4 5"/>
      <path d="M135 23V130" strokeDasharray="2 5" opacity=".4"/><circle cx="135" cy="90" r="4" fill="currentColor" stroke="none"/>
    </> : <>
      <rect x="58" y="28" width="154" height="103" rx="9"/><path d="M58 54H212M58 80H212M58 106H212M96 28V131M135 28V131M173 28V131"/>
      <path d="M36 45H22V142H190" opacity=".4"/>
      <path d="M107 67H124M146 93H162M185 119H202" strokeWidth="3" opacity=".45"/>
    </>}
  </svg>;
}

export function AssetCategoryCard({ title, description, subtitle, icon, index, kind, action, motif, tone = 'soft', onClick }: {
  title: string; description: string; subtitle?: string; icon: LucideIcon; index: number;
  kind: string; action: string; motif: AssetMotif; tone?: 'dark' | 'soft' | 'white'; onClick: () => void;
}) {
  return <CatalogCard title={title} description={description} subtitle={subtitle} icon={icon} index={index} kind={kind}
    action={action} onClick={onClick} className={`asset-category-card ${assetTheme(motif)} ${tone === 'white' ? '' : `catalog-tone-${tone}`}`}>
    <AssetArtwork motif={motif} />
  </CatalogCard>;
}
