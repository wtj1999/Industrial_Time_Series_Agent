import type { AgentDomain } from './domainConfig';
import type { ProductionGroupId } from './config';

type Composition = 'hero' | 'panel' | 'strip' | 'compact';

function EquipmentArtwork({ composition }: { composition: Composition }) {
  if (composition === 'hero') return <>
    <g opacity=".24" strokeWidth=".8"><path d="M20 40H440M20 80H440M20 120H440M20 160H440M60 20V180M140 20V180M220 20V180M300 20V180M380 20V180"/><path d="M32 24H48M40 16V32M420 160H436M428 152V168"/></g>
    <g transform="translate(348 102)"><circle r="68" strokeDasharray="3 7"/><circle r="53" strokeWidth="10" strokeDasharray="6 8" opacity=".45"/><circle r="39"/><circle r="22" strokeWidth="2"/><circle r="5" fill="currentColor" stroke="none"/><path d="M-78 0H-44M44 0H78M0-78V-44M0 44V78"/></g>
    <path d="M25 133H61L73 116 86 147 101 101 116 133H162L175 119 188 133H241" strokeWidth="2"/>
    <path d="M36 55H114L137 78H216L241 102H280M204 154H247L276 126H308"/>
    <g fill="currentColor" stroke="none"><circle cx="36" cy="55" r="3"/><circle cx="114" cy="55" r="3"/><circle cx="216" cy="78" r="3"/></g>
    <rect x="148" y="39" width="46" height="22" rx="4"/><path d="M157 50H165L170 44 177 55 184 50"/>
  </>;
  if (composition === 'panel') return <>
    <circle cx="111" cy="99" r="71" strokeDasharray="2 6"/><circle cx="111" cy="99" r="55" strokeWidth="11" strokeDasharray="5 9" opacity=".5"/><circle cx="111" cy="99" r="36"/><circle cx="111" cy="99" r="13" strokeWidth="2"/>
    <path d="M111 14V54M111 144V184M26 99H66M156 99H196M50 38L76 64M146 134L172 160"/>
    <path d="M18 157H45L56 144 68 170 81 151H99M150 38H177V63H198"/>
    <g fill="currentColor" stroke="none"><circle cx="177" cy="38" r="3"/><circle cx="198" cy="63" r="3"/></g>
  </>;
  return <>
    <rect x="31" y="28" width="82" height="50" rx="8"/><path d="M44 56H55L63 42 74 65 83 51H101M48 83V92H97V83M72 15V28M60 15H84"/>
    <circle cx="143" cy="47" r="24" strokeWidth="6" strokeDasharray="4 5" opacity=".5"/><circle cx="143" cy="47" r="12"/><path d="M115 47H129M157 47H175M143 19V33M143 61V75"/>
  </>;
}

function ProductionArtwork({ composition }: { composition: Composition }) {
  if (composition === 'hero') return <>
    <g opacity=".22" strokeWidth=".8"><path d="M12 134L210 25 454 133M12 158L210 49 454 157M52 180L250 71M112 180L310 98M172 180L370 124M232 180L430 150"/></g>
    <path d="M30 117L172 42 423 147 282 221Z" opacity=".35"/>
    <path d="M36 111L174 38 422 142 284 215Z" strokeWidth="2"/>
    <path d="M36 111V126L284 230 422 157V142M284 215V230"/>
    <g fill="currentColor" fillOpacity=".07" strokeWidth="1.4">
      <path d="M96 87L129 69 163 83 130 102ZM96 87V113L130 128 163 109V83M130 102V128"/>
      <path d="M176 87L209 69 243 83 210 102ZM176 87V113L210 128 243 109V83M210 102V128"/>
      <path d="M256 120L289 102 323 116 290 135ZM256 120V146L290 161 323 142V116M290 135V161"/>
      <path d="M337 153L370 135 404 149 371 168ZM337 153V179L371 194 404 175V149M371 168V194"/>
    </g>
    <path d="M130 45L164 27 224 52M242 60L302 85M320 93L377 117" strokeDasharray="4 5"/>
    <path d="M217 45L224 52 213 53M295 78L302 85 291 86M370 110L377 117 366 118"/>
  </>;
  if (composition === 'panel') return <>
    <path d="M25 68L105 27 191 69 111 111ZM25 68V83L111 126 191 84V69M111 111V126"/>
    <path d="M25 112L105 71 191 113 111 155ZM25 112V127L111 170 191 128V113M111 155V170" opacity=".5"/>
    <g fill="currentColor" fillOpacity=".07"><path d="M60 57L88 43 118 57 90 72ZM60 57V78L90 93 118 78V57M90 72V93"/><path d="M118 85L146 71 175 85 147 100ZM118 85V106L147 121 175 106V85M147 100V121"/></g>
    <path d="M39 146L111 183 179 148" strokeDasharray="3 5"/><path d="M169 147L179 148 177 157"/>
  </>;
  return <>
    <rect x="16" y="60" width="158" height="20" rx="10"/><path d="M27 70H163" strokeDasharray="2 8"/>
    <rect x="35" y="32" width="29" height="28" rx="3"/><rect x="82" y="23" width="29" height="37" rx="3"/><rect x="129" y="36" width="29" height="24" rx="3"/>
    <path d="M47 80V95M145 80V95M24 95H165M45 12H109L120 19M113 12L120 19 110 20"/>
  </>;
}

function MarketArtwork({ composition }: { composition: Composition }) {
  if (composition === 'hero') return <>
    <g opacity=".25"><path d="M20 158H447M20 119H447M20 80H447M20 41H447" strokeDasharray="2 6"/>
      <rect x="43" y="132" width="21" height="26" rx="2"/><rect x="86" y="110" width="21" height="48" rx="2"/><rect x="129" y="120" width="21" height="38" rx="2"/><rect x="172" y="88" width="21" height="70" rx="2"/><rect x="215" y="65" width="21" height="93" rx="2"/></g>
    <path d="M28 128L74 98 118 113 161 75 203 86 252 40" strokeWidth="2"/><path d="M237 42L252 40 250 55" strokeWidth="2"/>
    <g fill="currentColor" stroke="none"><circle cx="74" cy="98" r="3"/><circle cx="118" cy="113" r="3"/><circle cx="161" cy="75" r="3"/><circle cx="203" cy="86" r="3"/></g>
    <g transform="translate(357 96)"><circle r="67"/><ellipse rx="32" ry="67"/><ellipse rx="67" ry="24"/><path d="M-67 0H67M0-67V67M-55-37H55M-55 37H55" opacity=".65"/>
      <path d="M-59-34L-19 21 42-16 60 29" strokeWidth="1.6"/><g fill="currentColor" stroke="none"><circle cx="-59" cy="-34" r="4"/><circle cx="-19" cy="21" r="4"/><circle cx="42" cy="-16" r="4"/><circle cx="60" cy="29" r="4"/></g></g>
    <path d="M266 165C302 187 401 177 436 136" strokeDasharray="3 6"/>
  </>;
  if (composition === 'panel') return <>
    <circle cx="110" cy="96" r="64"/><ellipse cx="110" cy="96" rx="29" ry="64"/><ellipse cx="110" cy="96" rx="64" ry="23"/><path d="M46 96H174M110 32V160" opacity=".6"/>
    <path d="M55 64L91 115 143 76 165 129" strokeWidth="1.8"/>
    <g fill="currentColor" stroke="none"><circle cx="55" cy="64" r="4"/><circle cx="91" cy="115" r="4"/><circle cx="143" cy="76" r="4"/><circle cx="165" cy="129" r="4"/></g>
    <path d="M17 143C45 181 149 198 196 139M22 140L17 143 17 151" strokeDasharray="3 5"/>
  </>;
  return <>
    <g opacity=".55"><rect x="24" y="64" width="18" height="26" rx="2"/><rect x="61" y="45" width="18" height="45" rx="2"/><rect x="98" y="56" width="18" height="34" rx="2"/><rect x="135" y="23" width="18" height="67" rx="2"/></g>
    <path d="M16 58L53 31 89 41 130 13 160 24" strokeWidth="1.8"/>
    <g fill="currentColor" stroke="none"><circle cx="53" cy="31" r="3"/><circle cx="89" cy="41" r="3"/><circle cx="130" cy="13" r="3"/></g>
    <path d="M14 97H175M162 18L160 24 154 25"/>
  </>;
}

/** Decorative domain motifs; no application names, metrics or interactive content. */
export function DirectoryArtwork({ domain, groupId }: { domain: AgentDomain; groupId: ProductionGroupId }) {
  const composition: Composition = groupId === 'general' ? 'hero' : groupId === 'jinzhai-phase-3' ? 'panel' : groupId === 'jinzhai-phase-2' ? 'strip' : 'compact';
  const Artwork = domain === 'equipment' ? EquipmentArtwork : domain === 'production' ? ProductionArtwork : MarketArtwork;
  const viewBox = composition === 'hero' ? (domain === 'production' ? '0 0 480 240' : '0 0 480 200') : composition === 'panel' ? '0 0 220 200' : '0 0 190 110';
  return <svg className={`directory-artwork directory-artwork-${composition}`} data-domain={domain} viewBox={viewBox}
    fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    <Artwork composition={composition} />
  </svg>;
}
