'use strict';
/* Read-only presentation: every derived row keeps its source message ID. */
const MailViewModel=(()=>{
 const keyKinds=new Set(['goal','handoff','blocked','result','review_request','acknowledgement']);
 const labels={goal:'目标记录',handoff:'交接记录',blocked:'阻塞报告',result:'结果记录',review_request:'审核请求',acknowledgement:'确认记录',message:'消息',note:'备注'};
 const agent=value=>'@'+String(value||'unknown').replace(/^@/,'');
 const short=(value,max=100)=>{const s=String(value||'').replace(/\s+/g,' ').trim();return s.length>max?s.slice(0,max)+'…':s;};
 function receiptFact(record={}){
  const sessions=record.sessions||[];
  const state=sessions.some(s=>s.acknowledged_at)?'acknowledged':record.read_at?'read':sessions.some(s=>s.delivered_at)?'presented':'unobserved';
  return {...record,state,label:({acknowledged:'已确认',read:'已读',presented:'已呈现',unobserved:'未见呈现回执'})[state]};
 }
 function members(profiles=[],runtime=[]){
  const rows=new Map();
  profiles.filter(p=>p.kind!=='team'&&p.profile_kind!=='team').forEach(p=>{const id=agent(p.id);rows.set(id,{id,title:p.title,role:p.role||p.summary,profile:p});});
  runtime.forEach(a=>{const id=agent(a.agent_id);rows.set(id,{...(rows.get(id)||{id,title:id,role:'有可见通信记录，职责档案未记录'}),runtime:a});});
  return [...rows.values()];
 }
 function overview(item){const latest=item.latest||{};return {...item,id:item.thread_id,change:(labels[latest.record_kind]||latest.record_kind||'消息')+' · '+short(latest.title||latest.preview,70),status:labels[latest.record_kind]||'消息',tone:latest.record_kind==='blocked'?'amber':latest.record_kind==='result'?'blue':'',source_message_id:latest.message_id};}
 function thread(data){
  const messages=(data.messages||[]).map(m=>({...m,actor:agent(m.from),type:m.record_kind||'message',id:m.message_id}));
  const events=messages.filter(m=>keyKinds.has(m.type));const latest=messages.at(-1);const observation=data.observation||{};
  const goal=messages.find(m=>m.type==='goal');
  let attention={label:'当前关注',title:'接手人未明确',copy:'当前没有指定下一位接手者的明确记录。',event:latest,tone:'neutral'};
  if(latest?.type==='handoff'){
   const handoff=(observation.handoffs||[]).find(h=>h.message_id===latest.id);const recipients=handoff?.recipients||[];
   attention={label:'当前关注 · 交接',title:short(latest.title||'已有明确交接',65),copy:recipients.length?recipients.map(r=>`${r.agent_id} · ${r.label}`).join('；'):'交接收件人：'+(latest.to||[]).join('、'),event:latest,tone:'neutral'};
  }else if(latest?.type==='blocked')attention={label:'当前关注 · 阻塞报告',title:short(latest.title||'查看阻塞依据',65),copy:'请求发给 '+(latest.to||[]).join('、')+'。报告不表示后续已解决。',event:latest,tone:'amber'};
  else if(latest?.type==='result')attention={label:'当前关注 · 结果记录',title:short(latest.title||'结果已提交',65),copy:'已提交给 '+(latest.to||[]).join('、')+'。是否采纳以明确审核记录为准。',event:latest,tone:'blue'};
  else if(latest?.type==='review_request')attention={label:'当前关注 · 审核请求',title:short(latest.title||'请求人工审核',65),copy:'请查看请求原文与来源依据。',event:latest,tone:'amber'};
  const blockers=(observation.blockers||[]).map(b=>({...b,note:(b.follow_up_message_ids||[]).length?'已有显式回复，未据此判定解决':'尚未见直接回复；不推断执行状态'}));
  const refs=[];messages.forEach(m=>(m.evidence_refs||[]).forEach(ref=>{if(ref.path&&!refs.some(r=>r.path===ref.path))refs.push({...ref,source_message_id:m.id});}));
  return {...data,messages,events,history:messages.filter(m=>!keyKinds.has(m.type)),purpose:goal?short(goal.body,180):'尚未记录独立目标；以原始交接与请求为准。',purpose_source:goal?.id||null,latest,attention,blockers,refs};
 }
 function knowledge(map){
  const points=(map.domains||[]).flatMap(d=>(d.clusters||[]).flatMap(c=>(c.points||[]).map(p=>({...p,domain:d.label}))));
  const items=[...points,...(map.materials||[])].map(p=>({...p,id:p.path||p.id,tags:p.all_tags||p.tags||[],isMaterial:p.content_role==='source_material',isSkill:p.is_skill===true,knowledgeDomains:p.knowledge_domains||[{id:'_unmapped',label:'待对齐知识域'}],workerRecords:p.worker_records||[],reviewed:p.review?.reviewed===true}));
  const ids=new Set(items.map(p=>p.id));const merged=new Map();
  const explicit=map.explicit_edges||(map.edges||[]).filter(l=>(l.sources||[]).includes('知识条目自己声明的关系'));
  for(const link of [...explicit,...(map.internal_links||[]),...(map.material_edges||[])]){if(!ids.has(link.a)||!ids.has(link.b)||link.a===link.b)continue;const key=JSON.stringify([...[link.a,link.b].sort(),link.type]);const previous=merged.get(key);if(previous){previous.sources=[...new Set([...previous.sources,...(link.sources||[])])];previous.declared_by=[...new Set([...previous.declared_by,...(link.declared_by||[])])];}else merged.set(key,{...link,from:link.a,to:link.b,sources:[...(link.sources||[])],declared_by:[...(link.declared_by||[])]});}
  const links=[...merged.values()];
  const pair=(a,b)=>JSON.stringify([a,b].sort());
  const cited=new Set(links.map(l=>pair(l.from,l.to))),tagPairs=new Set();
  const tagLinks=(map.shared_tag_edges||[]).filter(l=>{
   const key=pair(l.a,l.b);if(!ids.has(l.a)||!ids.has(l.b)||l.a===l.b||cited.has(key)||tagPairs.has(key))return false;
   tagPairs.add(key);return true;
  }).map(l=>({...l,from:l.a,to:l.b,type:'shared_tag',type_label:'同标签关联',declared_by:[]}));
  return {items,links,tagLinks,truncated:!!map.scope?.truncated,total:map.scope?.points_total||items.length};
 }
 function resolveWikiLink(target,source,items){let raw=String(target||'').split('|')[0].split('#')[0].trim().replace(/\\/g,'/');try{raw=decodeURIComponent(raw);}catch{return null;}if(!raw||raw.startsWith('/')||/^[a-z][\w+.-]*:/i.test(raw))return null;const normalize=path=>{const parts=[];for(const p of path.split('/')){if(p==='..')parts.pop();else if(p&&p!=='.')parts.push(p);}return parts.join('/');};const candidates=[raw,normalize((source||'').split('/').slice(0,-1).join('/')+'/'+raw)].flatMap(p=>p.endsWith('.md')?[p]:[p,p+'.md']);const exact=items.find(p=>candidates.includes(p.path));if(exact)return exact;const name=raw.replace(/\.md$/,'').toLocaleLowerCase();const matches=items.filter(p=>p.title.toLocaleLowerCase()===name||p.path.split('/').at(-1).replace(/\.md$/,'').toLocaleLowerCase()===name);return !raw.includes('/')&&matches.length===1?matches[0]:null;}
 function matchesFields(item,filters={}){const active=Object.entries(filters).filter(([,v])=>v);if(!active.length)return true;const rows=item.workerRecords||[];if(!rows.length)return active.every(([,v])=>v==='__missing');return rows.some(r=>active.every(([key,value])=>value==='__missing'?!r.fields[key]:r.fields[key]===value));}
 function domainGroups(items){const groups=new Map();items.filter(p=>!p.isSkill&&!p.isMaterial).forEach(p=>(p.knowledgeDomains||[]).forEach(d=>{if(!groups.has(d.id))groups.set(d.id,{id:d.id,label:d.label,items:[]});const g=groups.get(d.id);if(!g.items.some(v=>v.id===p.id))g.items.push(p);}));return [...groups.values()].sort((a,b)=>(a.id==='_unmapped')-(b.id==='_unmapped')||b.items.length-a.items.length||a.label.localeCompare(b.label,'zh-CN'));}
 function sourceMaterialCollection(items=[]){
  const materials=items.filter(item=>item.isMaterial===true);
  const statusCounts={};let unreviewed=0;
  materials.forEach(item=>{const status=String(item.metadata?.ocr_review_status||'unknown');statusCounts[status]=(statusCounts[status]||0)+1;if(status==='unreviewed')unreviewed++;});
  return {id:'source-material-collection',title:'图片文字识别汇编',label:'来源资料集合',isDerivedCollection:true,count:materials.length,unreviewedCount:unreviewed,statusCounts,items:materials};
 }
 const fieldLabels={'评级':'采集评级','质量状态':'采集质量','Wiki状态':'采集端 Wiki 状态'};
 function threadSelection(data,selected,{changed=false,pinned=false}={}){
  if(pinned&&selected)return selected;
  if(!data)return changed?'':selected;
  if(data.items.some(row=>row.thread_id===selected))return selected;
  if(!changed&&data.page?.has_more&&selected)return selected;
  return data.items[0]?.thread_id||'';
 }
 function fieldOptions(items,key,active=''){
  const rows=items.flatMap(item=>item.workerRecords||[]);
  const values=[...new Set(rows.map(row=>row.fields?.[key]).filter(Boolean))].sort();
  if(!values.length&&!active)return [];
  if(items.some(item=>!item.workerRecords?.length||item.workerRecords.some(row=>!row.fields?.[key])))values.push('__missing');
  if(active&&!values.includes(active))values.push(active);
  return values;
 }
  return {agent,short,labels,keyKinds,overview,thread,knowledge,resolveWikiLink,matchesFields,domainGroups,sourceMaterialCollection,fieldLabels,threadSelection,fieldOptions,receiptFact,members};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=MailViewModel;
