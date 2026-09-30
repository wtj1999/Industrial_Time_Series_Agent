import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, X, Pause, Play } from 'lucide-react';
import type { SignalScene } from './signalScene';
import { SAMPLE_WINDOWS } from './signalSamples';
import { SignalDetailChart } from './SignalDetailChart';
const CHANNELS = ['温度','电流','振动','压力','转速'];
export function SignalCore({ paused, reducedMotion, onLogin }: { paused: boolean; reducedMotion: boolean; onLogin: () => void }) {
  const host = useRef<HTMLDivElement>(null), scene = useRef<SignalScene | null>(null);
  const [selected,setSelected]=useState(20), [detail,setDetail]=useState(false), [stop,setStop]=useState(false);
  const [status,setStatus]=useState<'loading'|'ready'|'fallback'>('loading'), [attempt,setAttempt]=useState(0);
  const latest=useRef({ selected, detail, paused:paused||stop, reducedMotion }); latest.current={ selected, detail, paused:paused||stop, reducedMotion };
  const row=selected%8,lane=Math.floor(selected/8),sample=SAMPLE_WINDOWS[row];
  useEffect(()=>{
    let cancelled=false, owned:SignalScene|null=null;
    const fail=()=>{ if(cancelled)return; owned?.dispose(); owned=null;scene.current=null;setStatus('fallback'); };
    import('./signalScene').then(async ({createSignalScene})=>{
      if(cancelled||!host.current)return;
      const result=await createSignalScene(host.current,latest.current,fail,index=>{setSelected(index);setDetail(true);setStop(false);});
      if(cancelled){result.dispose();return;} owned=result;scene.current=result;result.update(latest.current);setStatus('ready');
    }).catch(fail);
    return()=>{cancelled=true;owned?.dispose();if(scene.current===owned)scene.current=null;};
  },[attempt]);
  useEffect(()=>{scene.current?.update(latest.current);},[selected,detail,paused,stop,reducedMotion]);
  const choose=(index:number)=>{setSelected(index);setStop(false);};
  const open=()=>{setStop(false);setDetail(true);};
  return <section className={`temporal-stage ${detail?'is-detail':''}`} data-scene-status={status} aria-label="三维时序档案室">
    <div ref={host} className="temporal-world" />
    <div className="temporal-shade" />
    {status!=='ready' && <div className="temporal-loading" role="status"><span className="temporal-loading-line"/><p>{status==='loading'?'正在载入时序档案室…':'三维场景暂不可用'}</p>{status==='fallback'&&<button onClick={()=>{setStatus('loading');setAttempt(v=>v+1);}}>重新加载模型</button>}</div>}
    <div className="temporal-heading"><span>时序档案室 / 演示数据</span><h1>洞见工业脉搏，<br/>预见运行未来</h1><p>连接设备、工艺与生产数据，以自然语言探索异常、趋势与成因</p></div>
    {!detail && <nav className="temporal-lanes" aria-label="信号通道">{CHANNELS.map((name,i)=><button key={name} aria-pressed={i===lane} onClick={()=>choose(i*8+row)}><span>{String(i+1).padStart(2,'0')}</span>{name}<i/></button>)}</nav>}
    {!detail && <div className="temporal-selection"><span>{CHANNELS[lane]}通道 · 15 分钟采样窗口</span><h2>{sample.time}<em>—</em>{sample.end}</h2><p>{sample.name}<span>{sample.status}</span></p><button className="temporal-open" onClick={open}>抽取时间窗口 <ArrowRight size={16}/></button></div>}
    {detail && <aside className="temporal-detail" aria-label="时间窗口详情">
      <div className="temporal-detail-top"><span>采样窗口 / {String(row+1).padStart(2,'0')}</span><button onClick={()=>{setDetail(false);setStop(false);}} aria-label="返回全屏阵列"><X size={19}/></button></div>
      <div key={selected} className="temporal-document"><h2>{sample.time}<em>—</em>{sample.end}</h2><h3>{sample.name}</h3><p>{sample.note}</p>
      <SignalDetailChart windowIndex={row} />
      <dl>{sample.channels.map((name,i)=><div key={name}><dt>{name}</dt><dd>{sample.values[i]}</dd></div>)}</dl>
      </div>
      <button className="temporal-workspace" onClick={onLogin}>进入智能工作台 <ArrowRight size={16}/></button>
    </aside>}
    <footer className="temporal-timeline"><div className="temporal-timeline-caption"><span>采样时间</span><span>08:00 — 10:00 / 8 个窗口</span><button disabled={reducedMotion} aria-label={stop?'播放三维动画':'暂停三维动画'} onClick={()=>setStop(v=>!v)}>{stop||reducedMotion?<Play size={13}/>:<Pause size={13}/>}<span>{reducedMotion?'已减少动态':stop?'播放':'暂停'}</span></button></div>
      <div className="temporal-time-buttons"><button aria-label="上一个时间窗口" onClick={()=>choose(lane*8+(row+7)%8)}><ArrowLeft size={15}/></button>{SAMPLE_WINDOWS.map((s,i)=><button key={s.time} aria-label={`查看 ${s.time} 采样窗口`} aria-pressed={i===row} onClick={()=>choose(lane*8+i)}><i/><span>{s.time}</span></button>)}<button aria-label="下一个时间窗口" onClick={()=>choose(lane*8+(row+1)%8)}><ArrowRight size={15}/></button></div>
    </footer>
  </section>;
}
