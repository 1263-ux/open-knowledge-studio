const $=id=>document.getElementById(id);
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let threads=[],selected='',filter='all',drafts={},loading=true,connectionRequest='';
function current(){return threads.find(t=>t.thread_id===selected);}
function isHuman(id){return String(id).replace(/^@/,'')==='human';}
function name(id){return isHuman(id)?'你':String(id||'unknown').replace(/^@/,'');}
function avatar(id){return '<span class="avatar '+(isHuman(id)?'ink':'mint')+'">'+escapeHtml(name(id).slice(0,1))+'</span>';}
function toast(text){$('toast').textContent=text;setTimeout(()=>{$('toast').textContent='';},5000);}
async function api(path,payload){
 const response=await fetch('/api/mail/'+path,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const value=await response.json();if(!response.ok)throw new Error(value.error||'请求未完成');return value;
}
function renderList(){
 const rows=threads.filter(t=>(filter==='archived'?t.state==='archived':t.state!=='archived')&&(filter!=='unread'||t.unread_count>0)&&[t.title,...(t.participants||[])].join(' ').toLowerCase().includes($('search').value.toLowerCase()));
 $('total').textContent=threads.filter(t=>t.state!=='archived').length;$('unread').textContent=threads.filter(t=>t.unread_count>0&&t.state!=='archived').length;
 $('listTitle').textContent={all:'全部对话',unread:'未读消息',archived:'已归档'}[filter];
 document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('active',b.dataset.filter===filter);b.setAttribute('aria-pressed',String(b.dataset.filter===filter));});
 $('threadList').innerHTML=loading?'<div class="empty" role="status">正在读取邮箱…</div>':rows.length?rows.map(t=>'<button class="thread '+(t.thread_id===selected?'selected':'')+'" data-thread="'+escapeHtml(t.thread_id)+'"><div class="thread-top">'+avatar((t.participants||[]).find(p=>!isHuman(p)))+'<b>'+escapeHtml((t.participants||[]).map(name).join(' · '))+'</b><time>'+escapeHtml(new Date(t.last_at).toLocaleString())+'</time></div><h3>'+escapeHtml(t.title)+'</h3><p>'+escapeHtml(t.messages?.at(-1)?.body||'')+'</p>'+(t.unread_count?'<span class="tag">'+t.unread_count+' 条未读</span>':'')+'</button>').join(''):'<div class="empty"><h3>没有符合条件的对话</h3><p>切换筛选或新建对话。</p></div>';
}
function renderConversation(){
 const t=current();$('replyForm').hidden=!t;$('details').disabled=!t;$('archive').disabled=!t||t.state==='archived';
 $('subject').textContent=t?.title||'选择一段对话';$('participants').textContent=(t?.participants||[]).map(name).join(' / ');
 $('reply').value=drafts[selected]||'';$('replyError').textContent='';
 $('messages').innerHTML=t?(t.messages||[]).map(m=>'<article class="message '+(isHuman(m.from)?'mine':'')+'">'+avatar(m.from)+'<div class="message-content"><div class="message-meta"><b>'+escapeHtml(name(m.from))+'</b><time>'+escapeHtml(new Date(m.timestamp).toLocaleString())+'</time></div><div class="message-body">'+escapeHtml(m.body)+'</div>'+(m.read_at?'<p class="receipt">本地已读</p>':'')+'</div></article>').join(''):'<div class="empty">从左侧打开历史对话，或新建对话。</div>';
}
async function refresh(){
 const snapshot=await api('snapshot');threads=snapshot.threads||[];loading=false;
 if(!threads.some(t=>t.thread_id===selected))selected=threads[0]?.thread_id||'';
 if(selected){const full=await api('thread?id='+encodeURIComponent(selected));current().messages=full.messages;}
 renderList();renderConversation();$('syncLabel').textContent=snapshot.truncated?'显示最近 100 段对话；更早记录可由助手查阅':'当前知识库 · 已更新';
}
async function choose(id){
 selected=id;$('detailPanel').hidden=true;document.body.classList.add('reading');
 try{const full=await api('thread?id='+encodeURIComponent(id));if(selected!==id)return;current().messages=full.messages;renderList();renderConversation();for(const m of current()?.messages||[]){if(!isHuman(m.from)&&!m.read_at)await api('read',{message_id:m.message_id});}await refresh();}catch(error){toast(error.message);}
}
function openCompose(){$('newError').textContent='';$('composeDialog').showModal();}
$('new').onclick=openCompose;$('mobileNew').onclick=openCompose;
$('back').onclick=()=>document.body.classList.remove('reading');
$('search').oninput=renderList;
$('reply').oninput=()=>{drafts[selected]=$('reply').value;};
$('replyForm').onsubmit=async e=>{
 e.preventDefault();const body=$('reply').value.trim();if(!body)return;
 const threadId=selected;$('send').disabled=true;
 try{await api('reply',{thread_id:threadId,body});drafts[threadId]='';await refresh();toast('回复已保存');}
 catch(error){$('replyError').textContent=error.message;}finally{$('send').disabled=false;}
};
$('newForm').onsubmit=async e=>{
 e.preventDefault();const submit=e.submitter;submit.disabled=true;
 try{const result=await api('send',{title:$('newTitle').value.trim(),body:$('newBody').value.trim(),to:$('recipient').value.trim()});selected=result.thread_id;$('composeDialog').close();$('newForm').reset();document.body.classList.add('reading');await refresh();toast('消息已保存，等待对方读取');}
 catch(error){$('newError').textContent=error.message;}finally{submit.disabled=false;}
};
$('archive').onclick=async()=>{
 if(!current())return;$('archive').disabled=true;
 try{await api('archive',{thread_id:selected});await refresh();toast('已归档');}catch(error){toast(error.message);$('archive').disabled=false;}
};
$('details').onclick=()=>{
 const t=current();if(!t)return;
 $('detailContent').innerHTML='<h4>参与者</h4><p>'+escapeHtml((t.participants||[]).map(name).join(' · '))+'</p><h4>消息状态</h4><p>已保存在当前知识库。对方需要在会话中读取 Mail；保存不代表送达。</p><details><summary>来源与成果引用</summary><p>Thread：'+escapeHtml(t.thread_id)+'</p>'+(t.messages||[]).map(m=>'<p>'+escapeHtml(name(m.from))+' · Session '+escapeHtml(m.origin_session_id||'未记录')+' · Machine '+escapeHtml(m.origin_machine_id||'未记录')+'</p>'+((m.evidence_refs||[]).map(r=>'<p>'+escapeHtml(r.type)+': '+escapeHtml(r.id)+'</p>').join(''))).join('')+'</details>';
 $('detailPanel').hidden=false;$('details').setAttribute('aria-expanded','true');$('closeDetails').focus();
};
$('closeDetails').onclick=()=>{$('detailPanel').hidden=true;$('details').setAttribute('aria-expanded','false');$('details').focus();};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('detailPanel').hidden)$('closeDetails').click();});
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.thread)choose(b.dataset.thread);
 if(b.dataset.filter){filter=b.dataset.filter;renderList();}
 if(b.hasAttribute('data-close'))b.closest('dialog').close();
 if(b.dataset.view)switchWorkspace(b.dataset.view);
});
const rail=document.querySelector('.rail');
rail.querySelector('.logo').innerHTML='<span class="mark">o</span><span>OKS <strong>Mail</strong></span>';
rail.querySelectorAll('.contact').forEach(e=>e.hidden=true);
rail.querySelectorAll('.nav-label').forEach(e=>{if(e.textContent==='与我协作')e.hidden=true;});
const nav=document.createElement('div');nav.className='workspace-nav';
nav.innerHTML='<button data-view="mail">对话</button><button data-view="memory">记忆</button><button data-view="agents">助手与连接</button>';
rail.querySelector('.workspace').after(nav);
const mobileNav=nav.cloneNode(true);mobileNav.className='workspace-mobile';document.querySelector('.shell').before(mobileNav);
const page=document.createElement('section');page.id='workspacePage';page.hidden=true;document.querySelector('.shell').append(page);
function switchWorkspace(view){
 document.body.dataset.view=view;page.hidden=view==='mail';document.querySelector('.inbox').hidden=view!=='mail';$('conversation').hidden=view!=='mail';$('detailPanel').hidden=true;
 document.querySelectorAll('button[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);b.setAttribute('aria-current',b.dataset.view===view?'page':'false');});
 if(view==='memory')page.innerHTML='<header class="page-header"><div><h1>记忆</h1><p>Agent 通过 oks recall 查找当前知识库的相关记忆。</p></div></header><p>Mail 保存讨论历史，记忆由知识库管理。此页面尚未提供记忆浏览；请让助手使用 query Skill 查阅真实内容。</p>';
 if(view==='agents'){
  page.innerHTML='<header class="page-header"><div><h1>让助手帮你连接</h1><p>说说你想怎么协作，查找和配置交给助手。</p></div></header><section class="context-flow"><label class="field" for="connectionRequest">你想连接谁，一起做什么？<textarea id="connectionRequest" rows="4" placeholder="例如：让 Claude 和 Codex 都能给我留消息，换个会话也能接着聊。"></textarea></label><button id="handoffConnection" class="primary">复制需求，交给当前助手</button><p class="quiet-note" id="connectionStatus" role="status">复制后粘贴到你正在使用的助手对话中。助手会检查接入方式并完成配置；本页面不能直接控制该助手。</p><textarea id="connectionFallback" aria-label="手动复制连接需求" hidden readonly rows="6"></textarea></section><section class="connection-guide"><h2>你只需要说清需求</h2><p>助手负责查找接入方式、安装并检查邮箱。完成后会告诉你哪些助手已经能收发消息，还有什么需要处理。</p></section>';
  $('connectionRequest').value=connectionRequest;
  $('connectionRequest').oninput=e=>connectionRequest=e.target.value;
  $('handoffConnection').onclick=async()=>{
   if(!connectionRequest.trim()){$('connectionStatus').textContent='先写一句你想怎么协作。';$('connectionRequest').focus();return;}
   try{const guide=await api('connection-guide');const prompt='请帮我连接 OKS Mail。我的需求：\n'+connectionRequest+'\n当前知识库：'+JSON.stringify(guide.knowledge_base)+'\n请由你查找并配置接入方式，使用 oks-mail Skill 的连接指南。完成后验证邮箱可读，明确报告接入结果。\n'+guide.instructions;
    try{await navigator.clipboard.writeText(prompt);$('connectionStatus').textContent='需求已复制。粘贴给当前助手，由它完成连接。';}
    catch{$('connectionFallback').hidden=false;$('connectionFallback').value=prompt;$('connectionFallback').select();$('connectionStatus').textContent='请复制下方需求并粘贴给当前助手。';}
   }catch(error){$('connectionStatus').textContent=error.message;}
  };
 }

}
['labToggle','lab','help','theme','mobileHelp','mobileTheme','syncInfo'].forEach(id=>$(id).hidden=true);
document.querySelector('.demo>span').textContent='OKS Mail · 消息保存在当前知识库';
document.querySelector('.footnote').textContent='发送后写入知识库，由对方 Agent 在会话中读取。';
$('composeModeHint').textContent='写入当前知识库';
const refreshButton=document.createElement('button');refreshButton.textContent='刷新';refreshButton.type='button';
document.querySelector('.inbox>header').append(refreshButton);
refreshButton.onclick=async()=>{refreshButton.disabled=true;try{await refresh();}catch(error){toast(error.message);}finally{refreshButton.disabled=false;}};
switchWorkspace('mail');renderList();renderConversation();
refresh().catch(error=>{loading=false;renderList();$('syncLabel').textContent='读取失败，请刷新重试';toast(error.message);});


