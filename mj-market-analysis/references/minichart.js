// 轻量交互图表：SVG 自绘，悬停显示每个分类下所有系列的数值。无外部依赖。
(function(){
const C=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300','#6250d6','#e34948'];
const NS='http://www.w3.org/2000/svg';
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e;}
function fmt(v,u,d){if(v==null||isNaN(v))return '—';const n=d!=null?d:(Math.abs(v)>=100?0:(Math.abs(v)>=10?1:2));return v.toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n})+(u||'');}
function nice(max){if(max<=0)return 1;const p=Math.pow(10,Math.floor(Math.log10(max)));const m=max/p;for(const k of [1,1.2,1.5,2,2.5,3,4,5,6,8,10])if(m<=k)return k*p;return 10*p;}
const tip=document.createElement('div');
tip.style.cssText='position:fixed;pointer-events:none;background:#fff;border:1px solid #d6d5cf;border-radius:6px;padding:6px 9px;font:12px/1.5 -apple-system,PingFang SC,sans-serif;color:#0b0b0b;box-shadow:0 2px 8px rgba(0,0,0,.12);display:none;z-index:9;white-space:nowrap';
document.body.appendChild(tip);
function showTip(ev,html){tip.innerHTML=html;tip.style.display='block';const w=tip.offsetWidth,h=tip.offsetHeight;let x=ev.clientX+14,y=ev.clientY+14;if(x+w>window.innerWidth-4)x=ev.clientX-w-14;if(y+h>window.innerHeight-4)y=ev.clientY-h-14;tip.style.left=x+'px';tip.style.top=y+'px';}
function hideTip(){tip.style.display='none';}
function panel(root,P){
  const wrap=document.createElement('div');wrap.className='mc-panel';root.appendChild(wrap);
  const h=document.createElement('div');h.className='mc-title';h.textContent=P.title;wrap.appendChild(h);
  const W=780,hbar=P.type==='hbar';
  const n=P.categories.length;
  const H=P.height||(hbar?Math.max(220,n*26+40):280);
  const ml=hbar?(P.labelWidth||230):(P.ml||72),mr=16,mt=14,mb=hbar?28:(P.rotate?78:34);
  const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,width:'100%',style:'display:block;font:11px -apple-system,PingFang SC,sans-serif'},wrap);
  const pw=W-ml-mr,ph=H-mt-mb;
  const S=P.series;
  const V=S.filter(z=>z.kind!=='none');
  // value range
  let maxV=0,minV=0;
  if(P.type==='stack'){for(let i=0;i<n;i++){let s=0;V.forEach(z=>{s+=z.values[i]||0});maxV=Math.max(maxV,s);}}
  else V.forEach(z=>z.values.forEach(v=>{if(v!=null){maxV=Math.max(maxV,v);minV=Math.min(minV,v);}}));
  if(P.ymax!=null)maxV=P.ymax; if(P.ymin!=null)minV=P.ymin;
  const steps=5;
  const span=(maxV*1.08)-(minV<0?minV*1.08:0);
  const step=nice(span/steps);
  const top=Math.max(step,Math.ceil(maxV*1.08/step)*step), bot=minV<0?Math.floor(minV*1.08/step)*step:0;
  const nT=Math.round((top-bot)/step);
  const val2=v=>hbar? ml+(v-bot)/(top-bot)*pw : mt+ph-(v-bot)/(top-bot)*ph;
  for(let k=0;k<=nT;k++){const v=bot+step*k;
    if(hbar){const x=val2(v);el('line',{x1:x,x2:x,y1:mt,y2:mt+ph,stroke:'#ecebe7'},svg);const t=el('text',{x:x,y:H-8,'text-anchor':'middle',fill:'#6b6a65'},svg);t.textContent=fmt(v,'',step<1?1:0);}
    else{const y=val2(v);el('line',{x1:ml,x2:ml+pw,y1:y,y2:y,stroke:'#ecebe7'},svg);const t=el('text',{x:ml-6,y:y+4,'text-anchor':'end',fill:'#6b6a65'},svg);t.textContent=fmt(v,'',step<1?1:0);}}
  if(bot<0){const y=val2(0);el('line',{x1:ml,x2:ml+pw,y1:y,y2:y,stroke:'#52514e'},svg);}
  const band=(hbar?ph:pw)/n;
  const barS=S.filter(z=>(z.kind||(P.type==='line'?'line':'bar'))==='bar');
  const lineS=S.filter(z=>(z.kind||(P.type==='line'?'line':'bar'))==='line');
  // category labels
  const every=P.labelEvery||Math.max(1,Math.ceil(n/(hbar?60:16)));
  P.categories.forEach((c,i)=>{if(i%every)return;
    if(hbar){const t=el('text',{x:ml-6,y:mt+band*(i+.5)+4,'text-anchor':'end',fill:'#3a3936'},svg);t.textContent=c;}
    else{const x=ml+band*(i+.5);const multi=String(c).includes('\n');const t=el('text',{x:x,y:mt+ph+16,'font-size':multi?9:11,'text-anchor':P.rotate?'end':'middle',fill:'#52514e',transform:P.rotate?`rotate(-35 ${x} ${mt+ph+16})`:''},svg);
      String(c).split('\n').forEach((s,j)=>{const ts=el('tspan',{x:x,dy:j?12:0},t);ts.textContent=s;});}});
  // bars
  const gw=band*0.72, bw=P.type==='stack'?gw:gw/Math.max(1,barS.length);
  const base=new Array(n).fill(0);
  barS.forEach((z,si)=>{const col=z.color||C[S.indexOf(z)%8];
    z.values.forEach((v,i)=>{if(v==null)return;
      let a,b;
      if(P.type==='stack'){a=base[i];b=a+v;base[i]=b;}else{a=0;b=v;}
      const c=z.colors?z.colors[i]:col;
      if(hbar){const y=mt+band*i+(band-gw)/2+(P.type==='stack'?0:si*bw);el('rect',{x:val2(Math.min(a,b)),y:y,width:Math.abs(val2(b)-val2(a)),height:Math.max(1,bw-1),fill:c,rx:2},svg);}
      else{const x=ml+band*i+(band-gw)/2+(P.type==='stack'?0:si*bw);el('rect',{x:x+.5,y:val2(Math.max(a,b)),width:Math.max(1,bw-1),height:Math.abs(val2(b)-val2(a)),fill:c,rx:2},svg);}
      if(P.labels&&P.type!=='stack'){const t=el('text',{fill:'#3a3936','font-size':10.5},svg);
        if(hbar){t.setAttribute('x',val2(b)+4);t.setAttribute('y',mt+band*i+band/2+4);}else{t.setAttribute('x',ml+band*i+(band-gw)/2+si*bw+bw/2);t.setAttribute('y',v>=0?val2(b)-4:val2(b)+12);t.setAttribute('text-anchor','middle');}
        t.textContent=z.labelText?z.labelText[i]:fmt(v,z.unit!=null&&!P.unit?'':P.unit,z.decimals);}
    });});
  // lines
  lineS.forEach(z=>{const col=z.color||C[S.indexOf(z)%8];let d='';
    z.values.forEach((v,i)=>{if(v==null)return;const x=ml+band*(i+.5),y=val2(v);d+=(d?'L':'M')+x+' '+y;});
    el('path',{d:d,fill:'none',stroke:col,'stroke-width':2},svg);
    z.values.forEach((v,i)=>{if(v==null)return;el('circle',{cx:ml+band*(i+.5),cy:val2(v),r:n>40?2.2:3.5,fill:col,stroke:'#fff','stroke-width':1},svg);
      if(P.labels){const nb=[z.values[i-1],z.values[i+1]].filter(x=>x!=null);const low=nb.length&&v<Math.min(...nb)&&(v-bot)>0.18*(top-bot);
        const t=el('text',{x:ml+band*(i+.5),y:low?val2(v)+15:val2(v)-7,'text-anchor':'middle',fill:'#3a3936','font-size':10.5,'paint-order':'stroke',stroke:'#fcfcfb','stroke-width':3},svg);t.textContent=fmt(v,P.unit,z.decimals);}});});
  // hover targets
  const hl=el('rect',{fill:'#000','fill-opacity':0.05,visibility:'hidden'},svg);
  for(let i=0;i<n;i++){
    const r=hbar?el('rect',{x:ml,y:mt+band*i,width:pw,height:band,fill:'transparent'},svg):el('rect',{x:ml+band*i,y:mt,width:band,height:ph,fill:'transparent'},svg);
    r.addEventListener('mousemove',ev=>{
      if(hbar){hl.setAttribute('x',ml);hl.setAttribute('y',mt+band*i);hl.setAttribute('width',pw);hl.setAttribute('height',band);}
      else{hl.setAttribute('x',ml+band*i);hl.setAttribute('y',mt);hl.setAttribute('width',band);hl.setAttribute('height',ph);}
      hl.setAttribute('visibility','visible');
      let html='<b>'+String(P.tipCategories?P.tipCategories[i]:P.categories[i]).replace('\n',' ')+'</b>';
      S.forEach(z=>{const col=z.kind==='none'?'#c3c2b7':(z.colors?z.colors[i]:(z.color||C[S.indexOf(z)%8]));html+=`<br><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${col};margin-right:5px"></span>${z.name}：<b>${z.tipText?z.tipText[i]:fmt(z.values[i],z.unit!=null?z.unit:P.unit,z.decimals)}</b>`;});
      if(P.type==='stack'){let s=0;V.forEach(z=>s+=z.values[i]||0);html+=`<br>合计：<b>${fmt(s,P.unit)}</b>`;}
      if(P.extra&&P.extra[i])html+='<br><span style="color:#6b6a65">'+P.extra[i]+'</span>';
      showTip(ev,html);});
    r.addEventListener('mouseleave',()=>{hideTip();hl.setAttribute('visibility','hidden');});
  }
  // legend
  if(V.length>1||P.legend){const lg=document.createElement('div');lg.className='mc-legend';
    (P.legend||V.map(z=>({name:z.name,color:z.color||C[S.indexOf(z)%8],line:(z.kind||(P.type==='line'?'line':'bar'))==='line'}))).forEach(it=>{
      lg.insertAdjacentHTML('beforeend',`<span><i style="background:${it.color};${it.line?'height:3px;border-radius:2px':''}"></i>${it.name}</span>`);});
    wrap.appendChild(lg);}
}
window.MiniChart={render:function(spec){const root=document.getElementById('mc');
  const t=document.createElement('div');t.className='mc-h';t.textContent=spec.title;root.appendChild(t);
  spec.panels.forEach(p=>panel(root,p));
  const s=document.createElement('div');s.className='mc-src';s.textContent='数据来源：'+spec.source+'　鼠标悬停查看具体数值';root.appendChild(s);}};
})();
