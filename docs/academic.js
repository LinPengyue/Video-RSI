'use strict';
document.getElementById('copy-citation').addEventListener('click',async()=>{
  const text=document.getElementById('bibtex').textContent;
  const status=document.getElementById('copy-status');
  try{await navigator.clipboard.writeText(text);status.textContent='Citation copied to clipboard.';}
  catch{const selection=window.getSelection();const range=document.createRange();range.selectNodeContents(document.getElementById('bibtex'));selection.removeAllRanges();selection.addRange(range);status.textContent='Citation selected. Press Ctrl+C or ⌘C to copy.';}
});

const figureDialog=document.getElementById('figure-dialog'),viewer=document.getElementById('viewer-image');
const figures={framework:{src:'/Video-RSI/assets/overview.png',title:'Video-RSI framework',alt:document.querySelector('.framework img').alt},evolution:{src:'/Video-RSI/assets/evolution.svg',title:'Evolution over 20 revision attempts',alt:document.querySelector('.evolution-figure img').alt}};
let figureScale=1,figureTrigger;
function setZoom(scale){figureScale=Math.max(1,Math.min(4,scale));viewer.style.width=(figureScale*100)+'%';document.getElementById('zoom-level').value=Math.round(figureScale*100)+'%';document.getElementById('zoom-out').disabled=figureScale===1;document.getElementById('zoom-in').disabled=figureScale===4;}
document.querySelectorAll('[data-figure]').forEach(trigger=>trigger.addEventListener('click',e=>{e.preventDefault();figureTrigger=trigger;const figure=figures[trigger.dataset.figure];viewer.src=figure.src;viewer.alt=figure.alt;document.getElementById('figure-title').textContent=figure.title;const link=document.getElementById('original-figure');link.href=figure.src;figureDialog.showModal();document.body.style.overflow='hidden';setZoom(1);document.querySelector('.viewer-canvas').scrollTo(0,0);document.getElementById('close-figure').focus();}));
document.getElementById('zoom-in').addEventListener('click',()=>setZoom(figureScale+.5));document.getElementById('zoom-out').addEventListener('click',()=>setZoom(figureScale-.5));document.getElementById('zoom-reset').addEventListener('click',()=>setZoom(1));document.getElementById('close-figure').addEventListener('click',()=>figureDialog.close());figureDialog.addEventListener('close',()=>{document.body.style.overflow='';figureTrigger?.focus();});


// Paper-aligned animation: pre-edit investigation, candidate selection, retained harness.
(() => {
  const root=document.querySelector('.visual-teaser'),stage=root?.querySelector('.rsi-stage');if(!stage)return;
  const $=s=>root.querySelector(s),all=s=>[...root.querySelectorAll(s)];
  const svg=$('.rsi-connectors'),paths=Object.fromEntries(all('[data-route]').map(p=>[p.dataset.route,p]));
  const panels={solver:$('.rsi-solver'),editor:$('.rsi-editor'),gate:$('.rsi-gate')},video=$('.rsi-video'),packet=$('.rsi-packet'),signal=$('.rsi-signal');
  const frames=all('.rsi-frame'),button=$('.rsi-play'),scan=$('.rsi-scan');
  const explorer=$('.rsi-explorer'),cargo=$('.rsi-cargo'),closeup=$('.rsi-video-closeup'),beam=$('.rsi-look-beam'),homeBot=$('.rsi-editor h3 .rsi-bot'),proofs=all('.rsi-evidence-slot .rsi-proof'),sheet=$('.rsi-patch-sheet');let geometry;
  const solverAgent=$('.rsi-solver-agent'),solverHome=$('.rsi-solver h3 .rsi-bot'),observationPack=$('.rsi-observation-pack'),observations=all('.rsi-solver-proof'),reasonSteps=all('.rsi-reason-step'),reasonReturn=$('.rsi-reason-return');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');let elapsed=0,playing=!reduced.matches,visible=false,last=0,raf=0,ready=false;
  const clamp=x=>Math.max(0,Math.min(1,x));const ease=x=>{x=clamp(x);return x*x*(3-2*x)};
  const box=el=>{const r=el.getBoundingClientRect(),s=stage.getBoundingClientRect();return{x:r.x-s.x,y:r.y-s.y,w:r.width,h:r.height,cx:r.x-s.x+r.width/2,cy:r.y-s.y+r.height/2,right:r.right-s.x,bottom:r.bottom-s.y}};
  function layout(){
    const s=box(panels.solver),e=box(panels.editor),g=box(panels.gate),v=box(video),w=stage.clientWidth,h=stage.clientHeight,mobile=matchMedia('(max-width:780px)').matches;
    svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
    const labels=[];const label=(x,y,text)=>labels.push({x,y,text});
    if(!mobile){
      paths.input.setAttribute('d',`M${v.x} ${v.cy}H${s.cx}V${s.bottom}`);
      paths.trace.setAttribute('d',`M${s.right} ${s.cy}H${e.x}`);
      paths.revision.setAttribute('d',`M${e.right} ${e.cy}H${g.x}`);
      paths.return.setAttribute('d',`M${g.cx} ${g.y}V25H${s.cx}V${s.y}`);
      paths.feedback.setAttribute('d',`M${g.cx} ${g.bottom}V${g.bottom+44}H${(e.right+g.x)/2}V${e.cy+18}`);
      label((s.right+e.x)/2,s.cy-18,'Traces');label((s.right+e.x)/2,s.cy-4,'Results');label((e.right+g.x)/2,e.cy-13,'Revision');
      label((g.cx+e.right)/2,g.bottom+63,'Aggregate feedback');label((s.cx+v.x)/2,v.cy-11,'Video + question');
    }else{
      paths.input.setAttribute('d',`M${v.x} ${v.cy}H10V${s.cy}H${s.x}`);
      paths.trace.setAttribute('d',`M${s.cx} ${s.bottom}V${e.y}`);
      paths.revision.setAttribute('d',`M${e.right} ${e.cy}H${w-18}V${g.cy-40}H${g.right}`);
      paths.return.setAttribute('d',`M${g.right} ${g.cy}H${w-5}V23H${s.cx}V${s.y}`);
      paths.feedback.setAttribute('d',`M${g.x} ${g.cy+50}H21V${e.cy+50}H${e.x}`);
      label(s.cx+35,(s.bottom+e.y)/2+4,'Traces');
    }
    const xi=e.x+e.w*.32,xe=e.x+e.w*.72;
    paths.inspect.setAttribute('d',`M${xi} ${e.bottom}V${v.y}`);
    paths.evidence.setAttribute('d',`M${xe} ${v.y}V${e.bottom}`);

    label((s.cx+(mobile?w-5:g.cx))/2,16,'Selected harness');
    const group=$('.rsi-route-labels');group.replaceChildren();labels.forEach(l=>{const t=document.createElementNS('http://www.w3.org/2000/svg','text');t.setAttribute('x',l.x);t.setAttribute('y',l.y);t.setAttribute('text-anchor','middle');t.textContent=l.text;group.append(t)});
    geometry={s,e,g,v,home:box(homeBot),solverHome:box(solverHome),film:box($('.rsi-film')),frames:frames.map(box),slots:all('.rsi-evidence-slot').map(box),sheet:box(sheet)};
    ready=true;render();
  }
  function travel(name,q,color,asPacket=false){
    const path=paths[name],pt=path.getPointAtLength(path.getTotalLength()*ease(q));path.classList.add('is-active');
    if(asPacket){packet.style.opacity='1';packet.style.transform=`translate(${pt.x-14}px,${pt.y-16}px)`;packet.style.borderColor=color;packet.querySelectorAll('i').forEach(el=>el.style.background=color);}
    else{signal.setAttribute('cx',pt.x);signal.setAttribute('cy',pt.y);signal.setAttribute('fill',color);signal.setAttribute('opacity','1');}
  }
  const bezier=(a,b,c,d,t)=>({x:(1-t)**3*a.x+3*(1-t)**2*t*b.x+3*(1-t)*t*t*c.x+t**3*d.x,y:(1-t)**3*a.y+3*(1-t)**2*t*b.y+3*(1-t)*t*t*c.y+t**3*d.y});
  function robotAt(point,scale=1,angle=0){if(stage.clientWidth<480)point={...point,x:Math.max(29,Math.min(stage.clientWidth-(stage.dataset.phase==='investigate'?85:29),point.x))};explorer.style.opacity='1';explorer.style.transform=`translate(${point.x-26}px,${point.y-26}px) rotate(${angle}deg) scale(${scale})`;homeBot.style.opacity='0';}
  // One illustrative accepted attempt. The investigation is evidence-driven; no metrics are simulated.
  function render(){
    if(!ready)return;
    const t=(elapsed%40000)/1000,phase=t<6?'execute':t<23?'investigate':t<28?'revise':t<32?'select':t<34?'return':'transfer';
    const {s,e,v,home,solverHome:sh,frames:source,slots,sheet:patch}=geometry;
    const origin={x:home.cx,y:home.cy},start={x:sh.cx,y:sh.cy},watch={x:source[4].cx-29,y:v.y-25};
    stage.dataset.phase=phase;stage.dataset.newInput=String(t>=34);stage.dataset.reason='';$('.rsi-video-head>span:first-child').textContent=t>=34?'New video':'Training videos';
    Object.values(paths).forEach(el=>el.classList.remove('is-active'));
    all('.rsi-panel,.rsi-gate-step,.rsi-decision,.rsi-gate-compare').forEach(el=>el.classList.remove('is-active','is-chosen'));
    reasonSteps.forEach(el=>el.classList.remove('is-current'));reasonReturn.classList.remove('is-current');reasonReturn.querySelector('circle').style.opacity='0';
    signal.setAttribute('opacity','0');packet.style.opacity='0';scan.style.opacity='0';beam.setAttribute('opacity','0');$('.rsi-query-mark').style.opacity='0';
    explorer.style.opacity='0';homeBot.style.opacity='1';solverAgent.style.opacity='0';solverHome.style.opacity='1';cargo.style.opacity='0';cargo.style.transform='rotate(-6deg)';observationPack.style.opacity='0';observationPack.style.transform='none';closeup.style.opacity='0';$('.rsi-search-lens').style.opacity='0';$('.rsi-explorer-eyes').style.transform='none';
    const blue=phase==='execute'||phase==='transfer';beam.style.fill=blue?'#548cab18':'#cb944d18';beam.style.stroke=blue?'#548cab55':'#cb944d55';scan.style.background=blue?'#437e9e':'#b87b39';
    const execution=t>=34?t-34:t;
    frames.forEach((el,i)=>{el.classList.toggle('is-sampled',execution>1.4&&[1,4,7].includes(i));el.classList.remove('is-evidence','is-observed')});
    observations.forEach((el,i)=>{const q=clamp((execution-3.9-i*.12)/.28);el.style.opacity=String(q);el.style.transform=`translateY(${(1-q)*6}px)`;el.classList.toggle('is-matched',t>=13&&t<16&&i===1)});
    const answer=$('.rsi-answer'),answerMark=answer.querySelector('b');answer.style.opacity=String(clamp((execution-4.65)/.35));answerMark.style.opacity=String(clamp((execution-5.05)/.25));answer.classList.toggle('is-repaired',t>=34);answerMark.textContent=t>=34?'✓':'!';answerMark.setAttribute('aria-label',t>=34?'Evidence used in answer':'Failure feedback');
    const map=$('.rsi-memory-map');map.style.opacity=String(clamp((execution-4.1)/.35));$('.rsi-memory-base').style.opacity=t>=34?'.25':'1';$('.rsi-memory-gap').style.opacity=t>=34?'0':String(clamp((execution-4.5)/.3));$('.rsi-memory-fixed').style.strokeDashoffset=String(t>=34?180*(1-ease((execution-4.2)/.5)):180);$('.rsi-observations').classList.toggle('is-probed',t>=17.2&&t<19.1);
    all('.rsi-components span').forEach((el,i)=>{el.classList.toggle('is-used',execution<3.9&&execution>i*.12);el.classList.toggle('is-revised',t>=33.8&&i>=2)});
    $('.rsi-module-title').innerHTML=t>=33.8?'Harness H<sub>t+1</sub>':'Harness H<sub>t</sub>';
    all('.rsi-trace i').forEach((el,i)=>el.style.transform=`scaleX(${clamp((execution-5-i*.12)/.25)})`);
    const hypotheses=all('.rsi-hypothesis>span');hypotheses.forEach(el=>el.style.transform='none');hypotheses[0].classList.toggle('is-dismissed',t>=14.3);hypotheses[0].classList.toggle('is-focus',t>=6&&t<13);hypotheses[1].classList.toggle('is-focus',t>=15&&t<28);
    $('.rsi-hypothesis').style.opacity=t>=28?'.5':'1';
    all('.rsi-query-plan i').forEach((el,i)=>el.classList.toggle('is-target',t>=8&&t<13?i===1:t>=16&&t<20?i!==1:false));$('.rsi-query-plan>span').textContent=t>=16?'↻':'⌕';
    proofs[0].style.opacity=t>=13?'1':'0';proofs[1].style.opacity=t>=12.9?'1':'0';proofs.forEach(el=>el.style.transform='none');
    $('.rsi-same-evidence').style.opacity=t>=13.7?'1':'0';$('.rsi-evidence-slots').style.opacity=t>=20?'0':'1';$('.rsi-diagnosis-map').style.opacity=String(clamp((t-20)/.4));$('.rsi-diagnosis-link').style.transform=`scaleX(${t>=21?ease((t-21)/.6):0})`;
    const match=$('.rsi-match-route');match.setAttribute('opacity','0');
    sheet.style.opacity=t>=23?'1':'.28';sheet.classList.toggle('is-checking',t>=26.4&&t<28);$('.rsi-edit-pen').style.opacity='0';
    all('.rsi-patch-code i').forEach((el,i)=>{const q=clamp((t-23.6-i*.4)/.5);el.style.transform=`scaleX(${t>=23?.3+.7*q:1})`;el.style.background=t>=23&&q>.4?(i===1||i===2?'#9270a4':'#b9abc1'):'#c6c0cd'});
    const reason=name=>{stage.dataset.reason=name;$(`[data-reason="${name}"]`).classList.add('is-current')};
    const loop=q=>{const path=reasonReturn.querySelector('path'),pt=path.getPointAtLength(path.getTotalLength()*ease(q)),dot=reasonReturn.querySelector('circle');reasonReturn.classList.add('is-current');dot.setAttribute('cx',pt.x);dot.setAttribute('cy',pt.y);dot.style.opacity='1'};
    const lens=()=>{$('.rsi-search-lens').style.opacity='1';$('.rsi-explorer-eyes').style.transform='translateY(2px)'};
    const solverAt=(point,angle=0)=>{const x=Math.max(29,Math.min(stage.clientWidth-85,point.x));solverAgent.style.opacity='1';solverHome.style.opacity='0';solverAgent.style.transform=`translate(${x-26}px,${point.y-26}px) rotate(${angle}deg)`};
    const runSolver=(q,transfer)=>{
      if(q<.55)travel('input',q/.55,'#316f94');
      else if(q<1.4)solverAt(bezier(start,{x:s.x+26,y:start.y+120},{x:s.cx,y:v.y-40},watch,ease((q-.55)/.85)),3);
      else if(q<2.7){const u=(q-1.4)/1.3,index=[1,4,7][Math.min(2,Math.floor(u*3))],f=source[index];solverAt({x:watch.x+Math.sin(u*Math.PI)*7,y:watch.y},4);frames[index].classList.add('is-observed');scan.style.opacity='1';scan.style.left=(f.cx-geometry.film.x)+'px';beam.setAttribute('d',`M${watch.x+9} ${watch.y+17}L${f.x} ${f.y}L${f.right} ${f.y}Z`);beam.setAttribute('opacity','1');observationPack.style.opacity=String(clamp((q-2.3)/.3));}
      else if(q<3.9){const u=ease((q-2.7)/1.2);solverAt(bezier(watch,{x:s.cx,y:v.y-50},{x:s.x+28,y:start.y+120},start,u),-3*Math.sin(u*Math.PI));observationPack.style.opacity='1';}
      else if(q<4.4){solverAt(start);observationPack.style.opacity=String(1-ease((q-3.9)/.5));observationPack.style.transform=`translateY(${ease((q-3.9)/.5)*105}px)`;}
      else if(q>=5.35&&!transfer)travel('trace',(q-5.35)/.65,'#316f94',true);
    };
    if(phase==='execute'||phase==='transfer')runSolver(execution,phase==='transfer');
    else if(phase==='investigate'){
      if(t<8){reason('hypotheses');hypotheses.forEach((el,i)=>el.style.transform=`translateY(${-2*Math.sin(clamp((t-6-i*.25)/1.4)*Math.PI)}px)`);}
      else if(t<13){
        reason('queries');const q=t-8;
        if(q<1.1)robotAt(bezier(origin,{x:e.x-24,y:origin.y+65},{x:e.x-8,y:v.y-60},watch,ease(q/1.1)),1+.08*Math.sin(Math.PI*q/1.1));
        else if(q<2.9){const u=(q-1.1)/1.8;robotAt({x:watch.x+Math.sin(u*Math.PI)*9,y:watch.y},1.1,4);lens();[3,4,5].forEach(i=>frames[i].classList.add('is-evidence'));scan.style.opacity='1';scan.style.left=(source[3].x-geometry.film.x+u*(source[5].right-source[3].x))+'px';beam.setAttribute('d',`M${watch.x+9} ${watch.y+17}L${source[3].x} ${source[4].y}L${source[5].right} ${source[4].y}Z`);beam.setAttribute('opacity','1');closeup.style.left=Math.min(source[4].cx+13,v.right-96)+'px';closeup.style.top=(v.y-81)+'px';closeup.style.opacity=String(clamp((q-1.4)/.3));closeup.style.transform='none';}
        else if(q<4.3){const u=ease((q-2.9)/1.4);robotAt(bezier(watch,{x:e.right-5,y:v.y-65},{x:e.right-12,y:origin.y+75},origin,u),1.08-.08*u);cargo.style.opacity='1';}
        else{robotAt(origin);const slot=slots[1],u=ease((q-4.3)/.7);cargo.style.opacity=String(1-clamp((q-4.85)/.15));cargo.style.transform=`translate(${(slot.cx-origin.x-35.5)*u}px,${(slot.cy-origin.y-22)*u}px)`;proofs[1].style.opacity=String(clamp((q-4.8)/.2));}
      }else if(t<16){
        reason('diagnosis');const a=box(observations[1]),b=slots[0],u=ease((t-13)/.7);match.setAttribute('d',`M${a.cx} ${a.cy}C${a.cx+45} ${a.cy},${b.cx-55} ${b.cy},${b.cx} ${b.cy}`);match.setAttribute('pathLength','1');match.style.strokeDasharray='1';match.style.strokeDashoffset=String(1-u);match.setAttribute('opacity',String(t<15.2?1:clamp((16-t)/.8)));proofs[0].style.opacity=String(u);if(t>=15.1)loop((t-15.1)/.9);
      }else if(t<20){
        reason('queries');const q=t-16,obs=box($('.rsi-observations')),probe={x:obs.right-18,y:obs.cy-35};
        if(q<1.2)robotAt(bezier(origin,{x:e.x-25,y:origin.y+15},{x:s.right+10,y:probe.y},probe,ease(q/1.2)));
        else if(q<3){robotAt({x:probe.x,y:probe.y+Math.sin((q-1.2)*4)*2},1.05,5);lens();$('.rsi-query-mark').style.opacity='0';all('.rsi-trace i').forEach((el,i)=>el.style.transform=`scaleX(${.35+.65*clamp((q-1.2-i*.28)/.4)})`);}
        else{robotAt(bezier(probe,{x:s.right+15,y:probe.y+25},{x:e.x-15,y:origin.y+45},origin,ease(q-3)));}
      }else{reason('diagnosis');const map=$('.rsi-diagnosis-map');map.style.transform=`translateX(-50%) scale(${1+.04*Math.sin(clamp((t-20)/2)*Math.PI)})`;}
    }else if(phase==='revise'){
      const aim={x:patch.right+12,y:patch.y+25},u=ease((t-23)/.6);robotAt({x:origin.x+(aim.x-origin.x)*u,y:origin.y+(aim.y-origin.y)*u},1,5);$('.rsi-explorer-eyes').style.transform='translateY(2px)';const pen=$('.rsi-edit-pen');pen.style.opacity=t<26.2?'1':'0';pen.style.transform=`translate(${-12+Math.sin(t*9)*5}px,${Math.floor(clamp((t-23.6)/2)*3)*4-8}px)`;if(t>=27)travel('revision',t-27,'#86709c',true);
    }else if(phase==='select'){
      $('.rsi-gate-compare').classList.add('is-active');$('.rsi-private').classList.toggle('is-active',t<29.3);$('.rsi-metrics').classList.toggle('is-active',t>=29.3&&t<30.7);$('.rsi-decision').classList.toggle('is-active',t>=30.7);$('.rsi-decision').classList.toggle('is-chosen',t>=31);if(t>=31)travel('feedback',t-31,'#3b826b');
    }else{ $('.rsi-decision').classList.add('is-chosen');travel('return',(t-32)/2,'#316f94',true); }
    stage.dataset.playing=String(playing&&visible&&!document.hidden&&!figureDialog.open);button.textContent=playing?'Pause':'Play';button.setAttribute('aria-label',playing?'Pause framework animation':'Play framework animation');
  }
  function active(){return playing&&visible&&!document.hidden&&!figureDialog.open;}
  function tick(now){raf=0;if(!active()){last=0;return;}if(last)elapsed+=Math.min(now-last,100);last=now;render();raf=requestAnimationFrame(tick);}
  function sync(){if(raf)cancelAnimationFrame(raf);raf=0;last=0;render();if(active())raf=requestAnimationFrame(tick);}
  button.hidden=false;button.addEventListener('click',()=>{playing=!playing;sync();});reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;sync();}});document.addEventListener('visibilitychange',sync);
  figureDialog.addEventListener('close',sync);new MutationObserver(sync).observe(figureDialog,{attributes:true,attributeFilter:['open']});
  new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;sync();},{threshold:.12}).observe(stage);
  new ResizeObserver(layout).observe(stage);layout();
})();
