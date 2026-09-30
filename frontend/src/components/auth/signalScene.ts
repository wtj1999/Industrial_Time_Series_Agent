import { ModelRevealOverlay } from './ModelRevealOverlay';
import { ArchiveScene } from './rhine/scene';
import { fullMotion, reducedMotion } from './rhine/motion-preferences';
import { qualityPresets } from './rhine/render-quality';
export type SceneState = { selected: number; detail: boolean; paused: boolean; reducedMotion: boolean };
export type SignalScene = { update: (next: SceneState) => void; dispose: () => void };
export async function createSignalScene(host: HTMLElement, initial: SceneState, onFail: () => void, onSelect: (index: number) => void): Promise<SignalScene> {
  const scene = new ArchiveScene(host);
  const overlay = new ModelRevealOverlay(host);
  let state = initial, disposed = false, frame = 0, clock = 0, previous = performance.now(), opening = !initial.reducedMotion && !initial.detail, picked = false, lost = false;
  const canvas = scene.renderer.domElement;
  canvas.className = 'signal-core'; canvas.setAttribute('role','img');
  const onLost = (event: Event) => { event.preventDefault(); lost = true; onFail(); };
  canvas.addEventListener('webglcontextlost', onLost);
  const resize = new ResizeObserver(() => { if (!disposed) scene.resize(); });
  const dispose = () => {
    if (disposed) return;
    disposed = true; cancelAnimationFrame(frame); resize.disconnect(); overlay.dispose();
    canvas.removeEventListener('webglcontextlost',onLost); scene.dispose();
  };
  const applyMotion = () => scene.setMotion({ ...(state.reducedMotion ? reducedMotion() : fullMotion()), pointerParallax: false, dragMomentum: false, viewerNavigation: false, idleWave: !state.paused && !state.reducedMotion });
  try {
    await scene.load();
    if (lost) throw new Error("WebGL context lost while loading");
    scene.setQuality({ ...qualityPresets.original, antialias: 'smaa' });
    scene.setArchiveCoverage(true); scene.setTheme(false,true); applyMotion();
    scene.select(state.selected); scene.setMode(state.detail ? 'detail' : 'archive'); scene.resize(); resize.observe(host);
    if (!opening) scene.revealImmediately();
    scene.update(0);
    scene.onSelect = index => { picked = true; onSelect(index); };
    const update = (next: SceneState) => {
      const changed = state.selected !== next.selected, detailChanged = state.detail !== next.detail;
      state = next; applyMotion();
      if (changed || detailChanged || next.reducedMotion) opening = false;
      if (changed && !picked) scene.select(next.selected);
      picked = false;
      if (detailChanged || (changed && next.detail)) scene.setMode(next.detail ? 'detail' : 'archive');
      overlay.render(scene, next.detail && !next.reducedMotion);
    };
    const tick = (now: number) => {
      if (disposed) return;
      const dt = Math.min((now-previous)/1000,.1); previous=now;
      if (!document.hidden && !state.paused) {
        clock += dt;
        if (opening && clock < 5.2) scene.update(clock,{ reveal:1, lift:0, zoom:0, time:22+clock });
        else { if(opening) { opening=false; scene.revealImmediately(); } scene.update(clock); }
      }
      overlay.render(scene, state.detail && !state.reducedMotion);
      frame=requestAnimationFrame(tick);
    };
    frame=requestAnimationFrame(tick);
    return { update, dispose };
  } catch (error) { dispose(); throw error; }
}
