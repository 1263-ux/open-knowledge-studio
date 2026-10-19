'use strict';
let activeTagGraph=null;
const tagGraphViews=new Map();
function normalizeTag(value){return String(value||'').normalize('NFC').trim().replace(/^#+/,'').replace(/^\/+|\/+$/g,'').toLocaleLowerCase();}
function collectTagGroups(items,tagsOf=item=>item.tags||[]){
 const groups=new Map();
 items.forEach(item=>{const tags=tagsOf(item);(tags.length?tags:['未分类']).forEach(tag=>{const key=normalizeTag(tag);if(!key)return;let group=groups.get(key);if(!group){group={id:key,label:tag,items:[]};groups.set(key,group);}if(!group.items.some(p=>p.id===item.id))group.items.push(item);});});
 groups.forEach(group=>{group.items=items.filter(item=>matchesTag(item,group.label,tagsOf));});
 return [...groups.values()].sort((a,b)=>b.items.length-a.items.length||a.label.localeCompare(b.label,'zh-CN'));
}
function matchesTag(item,tag,tagsOf=item=>item.tags||[]){const key=normalizeTag(tag);const tags=tagsOf(item);return key==='未分类'?!tags.length:tags.some(value=>{const t=normalizeTag(value);return t===key||t.startsWith(key+'/');});}
function selectTagGraph(items,links,tag,context=false,tagsOf=item=>item.tags||[]){
 const direct=new Set(items.filter(item=>matchesTag(item,tag,tagsOf)).map(item=>item.id));const visible=new Set(direct);
 if(context)links.forEach(link=>{if(direct.has(link.from))visible.add(link.to);if(direct.has(link.to))visible.add(link.from);});
 const nodes=items.filter(item=>visible.has(item.id)).map(item=>({...item,inTag:direct.has(item.id)}));const ids=new Set(nodes.map(n=>n.id));
 return {nodes,links:links.filter(l=>ids.has(l.from)&&ids.has(l.to)),directCount:direct.size};
}
function getWikiTags(item){return item.tags||[];}
function graphLabel(title,limit=32){let width=0;let text='';for(const char of title){width+=char.charCodeAt(0)>255?2:1;if(width>limit)return text+'…';text+=char;}return text;}
function graphLabelPositions(labels,width,height,obstacles=[]){
 const overlaps=(a,b)=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;
 const boxes=[...obstacles],positions=new Map();
 for(const label of [...labels].sort((a,b)=>b.priority-a.priority)){
  const half=Math.min(label.width,width-24)/2;
  const x=Math.max(half+12,Math.min(width-half-12,label.x));
  if(label.x<0||label.x>width||label.y<0||label.y>height)continue;
  for(const [dx,dy] of [[0,24],[0,-26],[0,44],[0,-46],[-40,24],[40,24],[-40,-26],[40,-26],[0,64],[0,-66]]){
   const cx=Math.max(half+12,Math.min(width-half-12,x+dx)),y=label.y+dy,box={left:cx-half-4,right:cx+half+4,top:y-14,bottom:y+5};
   if(box.top<8||box.bottom>height-8||boxes.some(b=>overlaps(box,b)))continue;
   positions.set(label.id,{x:cx,y});boxes.push(box);break;
  }
 }
 return positions;
}
function tagColor(tag){const colors=['#647e6a','#677f94','#997d5e','#887b99','#6e9291','#9c7f7c'];let n=0;for(const c of normalizeTag(tag))n=(n*31+c.charCodeAt(0))>>>0;return colors[n%colors.length];}
function destroyTagGraph(){if(activeTagGraph){activeTagGraph.destroy();activeTagGraph=null;}}
function goTagOverview(push=true){state.page='wiki';state.global=true;state.graphTag=null;state.wikiOrigin=null;state.fieldFilters={};state.graphContext=false;state.query='';if(push)history.pushState(null,'','#wiki-overview&mode='+(state.knowledgeMode||'domains'));render();}
function goTagGraph(tag,push=true){if(wikiItems.find(p=>p.id===state.wiki)?.isMaterial)state.wiki='';state.page='wiki';state.global=true;state.graphTag=tag;state.wikiOrigin=null;state.query='';if(push)history.pushState(null,'',KnowledgeNavigation.graphHash(knowledgeOrigin({}),state.wiki));render();}
function tagMiniArt(items,color){
 const ns='http://www.w3.org/2000/svg';const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 260 89');svg.setAttribute('aria-hidden','true');svg.classList.add('tag-card-art');svg.style.color=color;
 const positions=[[130,40],[65,20],[190,20],[45,65],[205,65]];const count=Math.min(5,items.length);
 for(let i=1;i<count;i++){const l=document.createElementNS(ns,'line');l.setAttribute('x1','130');l.setAttribute('y1','40');l.setAttribute('x2',positions[i][0]);l.setAttribute('y2',positions[i][1]);svg.append(l);}
 positions.slice(0,count).forEach(([x,y],i)=>{const c=document.createElementNS(ns,'circle');c.setAttribute('cx',x);c.setAttribute('cy',y);c.setAttribute('r',i?4.5:7);svg.append(c);});return svg;
}
function renderTagOverview(scroll){renderKnowledgeOverview(scroll);}
function renderTagGraph(host,tag){
 const all=tag==='全部知识'||tag==='全部Skills'||tag==='skills:all';
 const domain=tag.startsWith('domain:'),skill=tag.startsWith('skills:');const domainKey=tag.slice(7);
 const pool=wikiItems.filter(p=>!p.isMaterial).filter(p=>VM.matchesFields(p,state.fieldFilters||{}));
 let data,titleText=tag;
 if(all){const skillScope=tag==='全部Skills'||tag==='skills:all';const nodes=pool.filter(p=>p.isSkill===skillScope);const ids=new Set(nodes.map(p=>p.id));data={nodes:nodes.map(p=>({...p,inTag:true})),links:wikiLinks.filter(l=>ids.has(l.from)&&ids.has(l.to)),directCount:nodes.length};titleText=skillScope?'全部 Skills':'全部知识';}
 else if(domain){data=selectTagGraph(pool,wikiLinks,domainKey,!!state.graphContext,p=>p.isSkill?[]:(p.knowledgeDomains||[]).map(d=>d.id));titleText=store.knowledge?.worker_source?.domain_options?.[domainKey]||(domainKey==='_unmapped'?'待对齐知识域':domainKey);}
 else if(skill){data=selectTagGraph(pool,wikiLinks,domainKey,!!state.graphContext,p=>p.isSkill?[p.governance?.type||'unclassified']:[]);titleText='Skills · '+(skillTypeNames[domainKey]||domainKey);}
 else data=selectTagGraph(pool.filter(p=>!p.isSkill),wikiLinks,tag,!!state.graphContext,getWikiTags);
 const view=e('section','tag-graph-view');const toolbar=e('header','tag-graph-toolbar');const title=e('div','tag-graph-title');title.append(button('← 分类总览','text-button',()=>goTagOverview()),e('h2',null,(all||domain||skill?'':'# ')+titleText),e('small',null,data.nodes.length+' 篇 · '+data.links.length+' 条链接'));toolbar.append(title);
 const controls=e('div','tag-graph-controls');const search=makeSearch('查找当前图谱',()=>{syncKnowledgeGraphRoute();updateHighlight();});controls.append(search);
 if(!all){const label=e('label','context-switch');const input=e('input');input.type='checkbox';input.checked=!!state.graphContext;input.setAttribute('aria-label','显示一跳关联');input.onchange=()=>{state.graphContext=input.checked;syncKnowledgeGraphRoute();render();};label.append(input,document.createTextNode('一跳关联'));controls.append(label);}
 const pause=button('暂停布局','button',()=>{paused=!paused;pause.textContent=paused?'继续布局':'暂停布局';pause.setAttribute('aria-pressed',String(paused));if(!paused){layout.reheat();start();}else{cancelAnimationFrame(frame);frame=0;draw();}});pause.setAttribute('aria-pressed','false');controls.append(pause);
 const settings=e('details','graph-settings');settings.append(e('summary','button','图谱设置'));const settingsBody=e('div','graph-settings-body');settingsBody.append(e('h3',null,'布局与连线'));settings.append(settingsBody);controls.append(settings);toolbar.append(controls);
 const stage=e('div','tag-graph-stage');stage.tabIndex=0;stage.setAttribute('aria-label','知识图谱画布，拖动节点或背景，使用加减号缩放');stage.style.setProperty('--tag-color',tagColor(tag));
 const ns='http://www.w3.org/2000/svg';const svg=document.createElementNS(ns,'svg');svg.setAttribute('role','group');svg.setAttribute('aria-label',tag+'动态图谱');const layer=document.createElementNS(ns,'g');svg.append(layer);stage.append(svg);
 const legend=e('div','graph-legend');legend.append(append(e('span'),e('i','graph-key'),e('span',null,all?'知识条目 · 悬停或放大查看名称':'当前分类')));if(data.nodes.some(n=>!n.inTag))legend.append(append(e('span'),e('i','graph-key context'),e('span',null,'一跳关联')));stage.append(legend);
 const hint=e('div','graph-hint',window.matchMedia('(pointer:coarse)').matches?'拖动节点 · 拖背景平移 · 双指缩放 · 轻点读正文':'拖动节点 · 滚轮缩放 · 拖背景平移 · 点击读正文');stage.append(hint);
 const searchEmpty=e('div','graph-search-empty','当前图谱没有匹配条目');searchEmpty.hidden=true;stage.append(searchEmpty);
 const zoomBar=e('div','graph-zoom');const zoomLabel=e('output',null,'100%');zoomLabel.setAttribute('aria-label','图谱缩放比例');zoomBar.append(button('−','',()=>zoomAt(zoom/1.2)),zoomLabel,button('＋','',()=>zoomAt(zoom*1.2)),button('适应','zoom-fit',()=>fit()));zoomBar.querySelector('button').setAttribute('aria-label','缩小图谱');zoomBar.querySelectorAll('button')[1].setAttribute('aria-label','放大图谱');stage.append(zoomBar);
 view.append(toolbar,stage);host.append(view);
 if(!data.nodes.length){stage.append(e('p','tag-empty','当前范围和筛选下暂无知识。'));pause.disabled=true;return;}
 const key=tag+'|'+Boolean(state.graphContext)+'|'+JSON.stringify(state.fieldFilters||{});const saved=tagGraphViews.get(key);
 const layout=createForceLayout(data.nodes,data.links);if(saved)layout.nodes.forEach(n=>{const old=saved.positions.get(n.id);if(old){n.x=old.x;n.y=old.y;}});
 let width=stage.clientWidth,height=stage.clientHeight,zoom=saved?.zoom||1,panX=saved?.panX||0,panY=saved?.panY||0,hover=null,frame=0,paused=false,destroyed=false;
 const reduced=window.matchMedia('(prefers-reduced-motion:reduce)');paused=reduced.matches||!!saved?.paused;pause.textContent=paused?'继续布局':'暂停布局';pause.setAttribute('aria-pressed',String(paused));
 const edgeElements=layout.edges.map(edge=>{const line=document.createElementNS(ns,'line');line.classList.add('force-edge');line.dataset.from=edge.from;line.dataset.to=edge.to;layer.append(line);return {edge,line};});
 const nodeElements=layout.nodes.map(node=>{const g=document.createElementNS(ns,'g');g.classList.add('force-node');if(!node.inTag)g.classList.add('context');if(node.kind==='candidate')g.classList.add('candidate');if(node.id===state.wiki)g.classList.add('selected');g.dataset.nodeId=node.id;g.dataset.path=node.path;g.setAttribute('tabindex','0');g.setAttribute('role','button');g.setAttribute('aria-label','阅读 '+node.title);g.style.setProperty('--node-color',node.inTag?tagColor(tag):'#a7b3a1');
  const hit=document.createElementNS(ns,'circle');hit.classList.add('node-hit');hit.setAttribute('r','24');const dot=document.createElementNS(ns,'circle');dot.classList.add('node-dot');const radius=7+Math.min(4,layout.edges.filter(l=>l.from===node.id||l.to===node.id).length);dot.setAttribute('r',String(radius));const text=document.createElementNS(ns,'text');text.textContent=graphLabel(node.title);text.setAttribute('y','29');const tooltip=document.createElementNS(ns,'title');tooltip.textContent=node.title+' · '+(node.inTag?'当前分类':'一跳关联')+' · 拖动或点击阅读';g.append(hit,dot,text,tooltip);
  g.addEventListener('pointerenter',()=>{hover=node.id;updateHighlight();});g.addEventListener('pointerleave',()=>{hover=null;updateHighlight();});g.addEventListener('focus',()=>{hover=node.id;updateHighlight();});g.addEventListener('blur',()=>{hover=null;updateHighlight();});g.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();openGraphArticle(node);}});layer.append(g);return {node,g,text,hit,dot,radius};});
 // Keep screen-size labels readable as real libraries grow. Every node remains
 // interactive; hover, keyboard focus and search take priority over other labels.
 function layoutLabels(){
  const q=search.querySelector('input').value.trim().toLocaleLowerCase(),connected=new Set();
  if(hover)layout.edges.forEach(l=>{if(l.from===hover)connected.add(l.to);if(l.to===hover)connected.add(l.from);});
  const screen=nodeElements.map(({node,text,radius})=>{text.style.display='';return {id:node.id,x:width/2+panX+node.x*zoom,y:height/2+panY+node.y*zoom,width:text.getComputedTextLength()*zoom,radius:Math.max(5,radius*zoom),priority:(node.id===hover?10000:0)+(q&&node.title.toLocaleLowerCase().includes(q)?1000:0)+(node.id===state.wiki?500:0)+(connected.has(node.id)?100:0),matches:!q||node.title.toLocaleLowerCase().includes(q)||node.id===hover};});
  const obstacles=screen.map(n=>({left:n.x-n.radius-4,right:n.x+n.radius+4,top:n.y-n.radius-4,bottom:n.y+n.radius+4}));
  const bounds=stage.getBoundingClientRect();
  for(const control of [legend,hint,zoomBar,searchEmpty]){if(control.hidden)continue;const r=control.getBoundingClientRect();obstacles.push({left:r.left-bounds.left-6,right:r.right-bounds.left+6,top:r.top-bounds.top-6,bottom:r.bottom-bounds.top+6});}
  const positions=graphLabelPositions(screen.filter(n=>n.matches),width,height,obstacles);
  nodeElements.forEach(({node,text})=>{const p=positions.get(node.id);text.style.display=p?'':'none';if(p){text.setAttribute('x',String((p.x-width/2-panX)/zoom-node.x));text.setAttribute('y',String((p.y-height/2-panY)/zoom-node.y));}});
  svg.dataset.visibleLabels=String(positions.size);
 }
 function draw(){if(destroyed)return;layer.setAttribute('transform',`translate(${width/2+panX} ${height/2+panY}) scale(${zoom})`);edgeElements.forEach(({edge,line})=>{line.setAttribute('x1',edge.source.x);line.setAttribute('y1',edge.source.y);line.setAttribute('x2',edge.target.x);line.setAttribute('y2',edge.target.y);});nodeElements.forEach(({node,g,text,hit,dot,radius})=>{g.setAttribute('transform',`translate(${node.x} ${node.y})`);text.textContent=graphLabel(node.title,width<600?20:32);text.style.fontSize=14/zoom+'px';text.style.strokeWidth=4/zoom+'px';dot.setAttribute('r',String(Math.max(radius,5/zoom)));hit.setAttribute('r',String(Math.max(24/zoom,14)));});layoutLabels();zoomLabel.value=Math.round(zoom*100)+'%';zoomLabel.textContent=zoomLabel.value;svg.dataset.alpha=layout.alpha.toFixed(4);svg.dataset.moving=String(Boolean(frame)&&!paused);svg.dataset.zoom=zoom.toFixed(3);}
 function tick(){frame=0;if(destroyed||paused)return;const moving=layout.step();if(moving)frame=requestAnimationFrame(tick);draw();}
 function start(){if(!frame&&!paused&&!destroyed){frame=requestAnimationFrame(tick);svg.dataset.moving='true';}}
 function fit(){if(!layout.nodes.length||width<1||height<1)return;const minX=Math.min(...layout.nodes.map(n=>n.x)),maxX=Math.max(...layout.nodes.map(n=>n.x)),minY=Math.min(...layout.nodes.map(n=>n.y)),maxY=Math.max(...layout.nodes.map(n=>n.y));zoom=Math.max(.1,Math.min(1.6,Math.max(50,width-120)/Math.max(160,maxX-minX),Math.max(50,height-190)/Math.max(160,maxY-minY)));panX=-(minX+maxX)/2*zoom;panY=-(minY+maxY)/2*zoom-12;draw();}
 function zoomAt(next,x=width/2,y=height/2){const z=Math.max(.1,Math.min(3.5,next));const wx=(x-width/2-panX)/zoom,wy=(y-height/2-panY)/zoom;panX=x-width/2-wx*z;panY=y-height/2-wy*z;zoom=z;draw();}
 function updateHighlight(){if(!nodeElements)return;const q=search.querySelector('input').value.trim().toLocaleLowerCase();const connected=new Set(hover?[hover]:[]);if(hover)layout.edges.forEach(l=>{if(l.from===hover)connected.add(l.to);if(l.to===hover)connected.add(l.from);});let matches=0;nodeElements.forEach(({node,g})=>{const match=!q||node.title.toLocaleLowerCase().includes(q);if(match)matches++;g.classList.toggle('dim',!match||(hover&&!connected.has(node.id)));g.classList.toggle('active',node.id===hover||(!!q&&match));});edgeElements.forEach(({edge,line})=>{line.classList.toggle('active',hover&&(edge.from===hover||edge.to===hover));line.classList.toggle('dim',!!hover&&edge.from!==hover&&edge.to!==hover);});searchEmpty.hidden=!q||matches>0;layoutLabels();}
 const sliders=[['center','中心聚拢',0,100,20,v=>v*.0003],['repel','节点排斥',0,100,40,v=>v*65],['link','连线牵引',0,100,30,v=>v*.0006],['distance','连线距离',80,320,180,v=>v]];
 sliders.forEach(([prop,label,min,max,value,convert])=>{const row=e('label');const output=e('output',null,String(value));const input=e('input');input.type='range';input.min=min;input.max=max;input.value=value;input.setAttribute('aria-label',label);input.oninput=()=>{output.value=input.value;layout.config[prop]=convert(Number(input.value));layout.reheat();if(paused){layout.settle();draw();}else start();};row.append(e('span',null,label),output,input);settingsBody.append(row);});settingsBody.append(e('p',null,'参数只影响布局，不修改条目标签与链接。'));
 const pointers=new Map();let gesture=null,pinch=null;
 function local(event){const rect=svg.getBoundingClientRect();return {x:event.clientX-rect.left,y:event.clientY-rect.top};}
 function world(p){return {x:(p.x-width/2-panX)/zoom,y:(p.y-height/2-panY)/zoom};}
 function beginPinch(){if(pointers.size!==2)return;const [a,b]=[...pointers.values()];const mid={x:(a.x+b.x)/2,y:(a.y+b.y)/2};pinch={distance:Math.max(1,Math.hypot(a.x-b.x,a.y-b.y)),zoom,world:world(mid)};if(gesture?.node){gesture.node.fx=null;gesture.node.fy=null;}gesture=null;}
 svg.addEventListener('pointerdown',event=>{if(event.button!==0)return;const p=local(event);pointers.set(event.pointerId,p);svg.setPointerCapture(event.pointerId);if(pointers.size===2){beginPinch();return;}const id=event.target.closest?.('.force-node')?.dataset.nodeId;const node=layout.nodes.find(n=>n.id===id);gesture={id:event.pointerId,start:p,node,panX,panY,moved:false};if(node){node.fx=node.x;node.fy=node.y;}svg.classList.add('dragging');event.preventDefault();});
 svg.addEventListener('pointermove',event=>{if(!pointers.has(event.pointerId))return;const p=local(event);pointers.set(event.pointerId,p);if(pointers.size===2&&pinch){const[a,b]=[...pointers.values()];const mid={x:(a.x+b.x)/2,y:(a.y+b.y)/2};zoom=Math.max(.25,Math.min(3.5,pinch.zoom*Math.hypot(a.x-b.x,a.y-b.y)/pinch.distance));panX=mid.x-width/2-pinch.world.x*zoom;panY=mid.y-height/2-pinch.world.y*zoom;draw();return;}if(!gesture||gesture.id!==event.pointerId)return;const dx=p.x-gesture.start.x,dy=p.y-gesture.start.y;if(Math.hypot(dx,dy)>5)gesture.moved=true;if(!gesture.moved)return;if(gesture.node){const w=world(p);gesture.node.fx=w.x;gesture.node.fy=w.y;gesture.node.x=w.x;gesture.node.y=w.y;layout.reheat();start();draw();}else{panX=gesture.panX+dx;panY=gesture.panY+dy;draw();}});
 function endPointer(event){pointers.delete(event.pointerId);if(pinch){pinch=null;gesture=null;pointers.clear();}if(gesture?.id===event.pointerId){const {node,moved}=gesture;if(node){node.fx=null;node.fy=null;if(moved){layout.reheat();start();}else if(event.type==='pointerup'){nodeElements.find(n=>n.node.id===node.id)?.g.focus({preventScroll:true});openGraphArticle(node);}}gesture=null;}svg.classList.remove('dragging');if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId);}
 svg.addEventListener('pointerup',endPointer);svg.addEventListener('pointercancel',endPointer);
 svg.addEventListener('wheel',event=>{event.preventDefault();const p=local(event);zoomAt(zoom*Math.exp(-event.deltaY*.0015),p.x,p.y);},{passive:false});
 stage.addEventListener('keydown',event=>{if(event.target.closest('input,button,summary'))return;const moves={ArrowLeft:[30,0],ArrowRight:[-30,0],ArrowUp:[0,30],ArrowDown:[0,-30]};if(moves[event.key]){event.preventDefault();panX+=moves[event.key][0];panY+=moves[event.key][1];draw();}else if(['+','=','-'].includes(event.key)){event.preventDefault();zoomAt(zoom*(event.key==='-'?1/1.2:1.2));}else if(event.key==='0'){event.preventDefault();fit();}});
 const observer=new ResizeObserver(()=>{const oldWidth=width;const oldHeight=height;width=stage.clientWidth;height=stage.clientHeight;if(width<oldWidth*.85||height<oldHeight*.75)fit();else draw();});observer.observe(stage);
 const onMotion=()=>{paused=reduced.matches;pause.textContent=paused?'继续布局':'暂停布局';pause.setAttribute('aria-pressed',String(paused));if(paused){cancelAnimationFrame(frame);frame=0;layout.settle();draw();}else{layout.reheat();start();}};reduced.addEventListener('change',onMotion);
 if(!saved){if(paused)layout.settle();else for(let i=0;i<28;i++)layout.step();fit();}else draw();start();updateHighlight();
 activeTagGraph={destroy(){tagGraphViews.set(key,{zoom,panX,panY,paused,positions:new Map(layout.nodes.map(n=>[n.id,{x:n.x,y:n.y}]))});destroyed=true;cancelAnimationFrame(frame);observer.disconnect();reduced.removeEventListener('change',onMotion);}};
}
if(typeof module!=='undefined'&&module.exports)module.exports={normalizeTag,collectTagGroups,matchesTag,selectTagGraph,graphLabelPositions};
