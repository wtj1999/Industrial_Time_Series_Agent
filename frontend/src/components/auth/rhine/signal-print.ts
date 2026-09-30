import * as THREE from 'three';

/** Shared illustrative signal sheet with qualitative analysis cues. */
export function createSignalPrint(anisotropy: number) {
  const canvas = document.createElement('canvas');
  canvas.width = 2048; canvas.height = 1280;
  const c = canvas.getContext('2d')!;
  const colors = ['#245ab2', '#167e96', '#6655a2'];
  const names = ['温度', '电流', '振动'];
  const left = 52, right = 1985, focus = .65;
  const wave = (t: number, ch: number) => {
    const peak = Math.exp(-Math.pow((t-.65)/.075,2));
    if(ch===0)return .24+.16*Math.sin(t*10-.8)+.075*Math.sin(t*22)+.35*peak;
    if(ch===1)return .18+.07*Math.sin(t*24)+.05*Math.sin(t*47)+.66*peak;
    return .18+.075*Math.sin(t*48)+.055*Math.sin(t*77)+.28*peak;
  };
  const text=(value:string,x:number,y:number,size=34,color='#2c405d')=>{
    c.font=`600 ${size}px "Segoe UI", "Microsoft YaHei", sans-serif`;
    c.fillStyle=color;c.fillText(value,x,y);
  };
  const line=(x:number,y:number,x2:number,y2:number,color='#9bb1cd',width=2)=>{
    c.strokeStyle=color;c.lineWidth=width;c.beginPath();c.moveTo(x,y);c.lineTo(x2,y2);c.stroke();
  };
  const path=(points:number[][])=>{c.beginPath();points.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));};
  text('多通道信号',left,47,44,'#233750');
  text('归一化幅值',left+310,47,34);
  c.textAlign='right';text('示意窗口',right,47,34);c.textAlign='left';
  // A single observation window aligns all three channels.
  const bandX=left+(right-left)*.58, bandWidth=(right-left)*.14;
  const band=c.createLinearGradient(bandX,0,bandX+bandWidth,0);
  band.addColorStop(0,'#84aceb09');band.addColorStop(.5,'#84aceb30');band.addColorStop(1,'#84aceb09');
  c.fillStyle=band;c.fillRect(bandX,85,bandWidth,820);
  c.setLineDash([6,10]);line(left+(right-left)*focus,85,left+(right-left)*focus,905,'#648abe',2);c.setLineDash([]);
  for(let ch=0;ch<3;ch++){
    const top=99+ch*277,base=top+233;
    text(names[ch],left,top+30,43,'#263d5c');
    const pts=Array.from({length:641},(_,i)=>[left+(right-left)*i/640,base-24-wave(i/640,ch)*173]);
    const wash=c.createLinearGradient(0,top+40,0,base);
    wash.addColorStop(0,colors[ch]+'45');wash.addColorStop(1,colors[ch]+'00');
    path(pts);c.lineTo(right,base);c.lineTo(left,base);c.closePath();c.fillStyle=wash;c.fill();
    line(left,base,right,base,'#a3b7d0',1.5);
    for(let i=0;i<=20;i++)line(left+(right-left)*i/20,base+7,left+(right-left)*i/20,base+(i%5===0?18:11),'#9eb2ce',1.5);
    path(pts);c.strokeStyle=colors[ch];c.lineWidth=9;c.lineJoin='round';c.lineCap='round';c.stroke();
    const [x,y]=pts[416];c.beginPath();c.arc(x,y,12,0,Math.PI*2);c.fillStyle='#edf4ff';c.fill();c.strokeStyle=colors[ch];c.lineWidth=4;c.stroke();
  }
  text('窗口起点',left,952,34);
  c.textAlign='center';text('相对时间', (left+right)/2,952,34);
  c.textAlign='right';text('窗口终点',right,952,34);c.textAlign='left';
  // Qualitative reading cues remain meaningful for the shared illustrative model.
  line(left,1003,right,1003,'#91a9c8',2);
  const cues = [
    ['趋势观察', '追踪信号随时间的变化'],
    ['波动识别', '捕捉局部起伏与突变'],
    ['通道关联', '对照同一时刻的信号响应'],
  ];
  cues.forEach(([title,description],index)=>{
    const x=left+index*665;
    line(x,1065,x+55,1065,colors[index],5);
    text(title,x,1125,44,'#263d5c');
    text(description,x,1182,36);
  });
  const texture=new THREE.CanvasTexture(canvas);
  texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=anisotropy;
  const material=new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false,opacity:0,toneMapped:false});
  const print=new THREE.Mesh(new THREE.PlaneGeometry(4.10,2.40),material);
  print.name='Signal print';print.userData.signalPrint=true;print.position.set(0,1.52,.255);
  return print;
}
