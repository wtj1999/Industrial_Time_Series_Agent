import type { ArchiveScene } from './rhine/scene';
import { DECRYPTION_START, DECRYPTION_END, SCAN_FROM, SCAN_TO, SCAN_CORNERS } from './rhine/decryption';

/** Project the reference reveal choreography onto the actual moving cassette. */
export class ModelRevealOverlay {
  private root = document.createElement('div');
  private svg: SVGSVGElement;
  private lines: SVGPathElement;
  private corners: SVGPathElement;
  private sweep: SVGPathElement;
  private label: HTMLDivElement;
  private progress: HTMLElement;
  private title: HTMLElement;
  constructor(private host: HTMLElement) {
    this.root.className = 'model-reveal-overlay';
    this.root.setAttribute('aria-hidden', 'true');
    this.root.innerHTML = `<svg><path class="model-reveal-corners"/><path class="model-reveal-lines"/><path class="model-reveal-sweep"/></svg><div class="model-reveal-label"><span>信号扫描</span><strong>00%</strong><i><b></b></i></div>`;
    this.svg = this.root.querySelector('svg')!;
    this.lines = this.root.querySelector('.model-reveal-lines')!;
    this.corners = this.root.querySelector('.model-reveal-corners')!;
    this.sweep = this.root.querySelector('.model-reveal-sweep')!;
    this.label = this.root.querySelector('.model-reveal-label')!;
    this.progress = this.label.querySelector('b')!;
    this.title = this.label.querySelector('span')!;
    host.appendChild(this.root);
  }
  render(scene: ArchiveScene, enabled: boolean) {
    const frame = scene.decryptionFrame;
    const active = enabled && frame.phase !== 'clear';
    this.root.dataset.phase = enabled ? frame.phase : 'idle';
    this.root.style.opacity = active ? String(Math.max(.2, scene.detailVisibility)) : '0';
    if (!active) return;
    this.svg.setAttribute('viewBox', `0 0 ${this.host.clientWidth} ${this.host.clientHeight}`);
    const project = (x: number, y: number) => scene.projectCard(x,y).map(v => v.toFixed(2)).join(',');
    const at = (t: number) => project(SCAN_FROM[0]+(SCAN_TO[0]-SCAN_FROM[0])*t, SCAN_FROM[1]+(SCAN_TO[1]-SCAN_FROM[1])*t);
    this.lines.setAttribute('d', frame.intervals.map(([a,b])=>`M${at(a)}L${at(b)}`).join(''));
    this.corners.setAttribute('d', SCAN_CORNERS.map(([x,y])=>{
      const dx=x<0?.13:-.13,dy=y<1?.13:-.13;
      return `M${project(x+dx,y)}L${project(x,y)}L${project(x,y+dy)}`;
    }).join(''));
    this.corners.style.opacity = String(Math.max(.22,frame.markers));
    const y=3.7*(1-frame.clarity);
    this.sweep.setAttribute('d',frame.phase==='revealing'?`M${project(-2.25,y)}L${project(2.25,y)}`:'');
    const [xLabel,yLabel]=scene.projectCard(0,1.85);
    this.label.style.transform=`translate(${xLabel}px,${yLabel}px) translate(-50%,-50%)`;
    const value=Math.max(0,Math.min(1,(frame.time-DECRYPTION_START)/(DECRYPTION_END-DECRYPTION_START)));
    this.label.querySelector('strong')!.textContent=`${Math.round(value*100).toString().padStart(2,'0')}%`;
    this.progress.style.transform=`scaleX(${value})`;
    this.title.textContent=frame.phase==='waiting'?'正在抽取':frame.phase==='revealing'?'正在显露':'信号扫描';
    this.label.style.opacity=String(1-frame.clarity);
  }
  dispose() { this.root.remove(); }
}
