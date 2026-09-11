const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let threads = [];
let selected = '';
let filter = 'all';
let drafts = {};
let loading = true;
let workspaceView = 'mail';
let connection = null;

const mobileNav = document.querySelector('.workspace-mobile');
mobileNav.innerHTML = document.querySelector('.workspace-nav').innerHTML;
mobileNav.querySelector('.workspace-nav-title')?.remove();

function isHuman(id) { return String(id || '').replace(/^@/, '').toLowerCase() === 'human'; }
function name(id) { return isHuman(id) ? '你' : String(id || 'unknown').replace(/^@/, ''); }
function avatar(id) { return `<span class="avatar ${isHuman(id) ? 'ink' : 'mint'}">${escapeHtml(name(id).slice(0, 1))}</span>`; }
function senderKind(message) {
  const raw = String(message?.sender_kind || '').toLowerCase();
  if (raw === 'human' || isHuman(message?.from)) return {label:'人', className:'human'};
  if (raw === 'agent') return {label:'Agent', className:'agent'};
  if (raw === 'system') return {label:'系统', className:'system'};
  return {label:'来源未标注', className:'unknown'};
}
function senderLabel(message) {
  const kind = senderKind(message);
  return `<span class="sender-name">${escapeHtml(name(message?.from))}</span><span class="sender-kind ${kind.className}">${kind.label}</span>`;
}
function threadMachines(thread) {
  return new Set((thread?.messages || []).map(message => message.origin_machine_id).filter(machine => machine && machine !== 'unknown'));
}
function current() { return threads.find(thread => thread.thread_id === selected); }
function isVisibleThread(thread) {
  if (filter === 'archived') return thread.state === 'archived';
  if (thread.state === 'archived') return false;
  return filter !== 'unread' || thread.unread_count > 0;
}
function toast(text) { $('toast').textContent = text; window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => { $('toast').textContent = ''; }, 5000); }
function formatTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value || '') : date.toLocaleString('zh-CN', {month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit'});
}
async function api(path, payload) {
  const response = await fetch(`/api/mail/${path}`, payload === undefined ? {cache:'no-store'} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  let value = {};
  try { value = await response.json(); } catch { /* keep the HTTP error useful */ }
  if (!response.ok) throw new Error(value.error || `请求失败（${response.status}）`);
  return value;
}

function conversationModes(thread) {
  const participants = (thread?.participants || []).filter(participant => !isHuman(participant));
  const machines = threadMachines(thread);
  const modes = [{label:'现在可继续', detail:'回复会留在同一段对话里。', kind:'available'}];
  if (participants.length > 1) modes.push({label:'多人对话', detail:'这段对话包含多个参与身份。', kind:'available'});
  else if (participants.length === 1) modes.push({label:`和 ${name(participants[0])} 对话`, detail:'你和这个 Agent 共享同一段对话。', kind:'available'});
  if (machines.size > 1) modes.push({label:`跨机器已发生（${machines.size} 台）`, detail:'这段对话的消息记录了多台设备来源；Git 同步仍需由你或 Agent 执行。', kind:'available'});
  else modes.push({label:'未发现跨机器记录', detail:'目前只看到一台或未知设备来源；Mail 不会自动判断 Git 是否已同步。', kind:'pending'});
  return modes;
}

function renderList() {
  const query = $('search').value.trim().toLowerCase();
  const rows = threads.filter(thread =>
    isVisibleThread(thread) &&
    [thread.title, ...(thread.participants || [])].join(' ').toLowerCase().includes(query));
  $('total').textContent = threads.filter(thread => thread.state !== 'archived').length;
  $('unread').textContent = threads.filter(thread => thread.unread_count > 0 && thread.state !== 'archived').length;
  $('listTitle').textContent = {all:'全部对话', unread:'未读消息', archived:'已归档'}[filter];
  document.querySelectorAll('[data-filter]').forEach(button => {
    const active = button.dataset.filter === filter;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  if (loading) { $('threadList').innerHTML = '<div class="empty" role="status">正在读取邮箱…</div>'; return; }
  if (!rows.length) { $('threadList').innerHTML = '<div class="empty"><h3>这里还没有对话</h3><p>新建一段对话，消息会写入当前知识库。</p><button class="primary" data-create>新建对话</button></div>'; return; }
  $('threadList').innerHTML = rows.map(thread => {
    const people = (thread.participants || []).filter(participant => !isHuman(participant));
    const latest = thread.messages?.at(-1) || {from: people[0] || 'unknown', sender_kind: people.length ? 'agent' : 'human'};
    const mode = people.length > 1 ? '多人对话' : people.length === 1 ? '持续对话' : '我的消息';
    return `<button class="thread ${thread.thread_id === selected ? 'selected' : ''}" data-thread="${escapeHtml(thread.thread_id)}"><div class="thread-top">${avatar(latest.from)}<b class="thread-sender">${senderLabel(latest)}</b><time>${escapeHtml(formatTime(thread.last_at))}</time></div><h3>${escapeHtml(thread.title)}</h3><p>${escapeHtml(latest.body || '')}</p><span class="tag">${escapeHtml(mode)}</span>${thread.unread_count ? `<span class="tag unread-tag">${thread.unread_count} 条未读</span>` : ''}</button>`;
  }).join('');
}

function renderConversation() {
  const thread = current();
  const box = $('messages');
  const previousThread = box.dataset.thread || '';
  const wasNearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  $('replyForm').hidden = !thread;
  $('moreActions').disabled = !thread;
  $('archive').disabled = !thread || thread.state === 'archived';
  $('archive').hidden = !thread || thread.state === 'archived';
  $('unarchive').hidden = !thread || thread.state !== 'archived';
  $('details').hidden = !thread;
  const archiveAction = document.querySelector('[data-thread-action="archive"]');
  const unarchiveAction = document.querySelector('[data-thread-action="unarchive"]');
  if (archiveAction) archiveAction.hidden = !thread || thread.state === 'archived';
  if (unarchiveAction) unarchiveAction.hidden = !thread || thread.state !== 'archived';
  $('subject').textContent = thread?.title || '选择一段对话';
  $('participants').textContent = (thread?.participants || []).map(name).join(' / ');
  $('conversationModes').innerHTML = thread ? conversationModes(thread).map(mode => `<span class="mode-chip ${mode.kind}" title="${escapeHtml(mode.detail)}">${escapeHtml(mode.label)}</span>`).join('') : '';
  $('reply').value = drafts[selected] || '';
  $('replyError').textContent = '';
  $('messages').innerHTML = thread ? (thread.messages || []).map(message => `<article class="message ${isHuman(message.from) ? 'mine' : ''}">${avatar(message.from)}<div class="message-content"><div class="message-meta"><b class="message-sender">${senderLabel(message)}</b><time>${escapeHtml(formatTime(message.timestamp))}</time></div><div class="message-body">${escapeHtml(message.body)}</div>${message.read_at ? '<p class="receipt">本地已读</p>' : ''}</div></article>`).join('') : '<div class="empty"><h3>重要的对话，都留在这里</h3><p>从左侧打开历史对话，或新建一段对话。</p></div>';
  $('replyTo').textContent = thread ? '回复这段对话' : '';
  if (thread) window.requestAnimationFrame(() => {
    if (previousThread !== thread.thread_id || wasNearBottom) box.scrollTop = box.scrollHeight;
    box.dataset.thread = thread.thread_id;
  });
}

async function refresh() {
  const snapshot = await api('snapshot');
  threads = snapshot.threads || [];
  loading = false;
  if (!threads.some(thread => thread.thread_id === selected && isVisibleThread(thread))) selected = threads.find(isVisibleThread)?.thread_id || '';
  if (selected) current().messages = (await api(`thread?id=${encodeURIComponent(selected)}`)).messages || [];
  renderList(); renderConversation();
  $('syncLabel').textContent = snapshot.truncated ? '显示最近 100 段；更早记录由 Agent 查阅' : '当前知识库 · 已更新';
  $('runtimeText').textContent = '真实 Mail · 消息读写当前知识库';
}

async function choose(threadId) {
  selected = threadId;
  document.body.classList.add('reading');
  $('detailPanel').hidden = true;
  try {
    const full = await api(`thread?id=${encodeURIComponent(threadId)}`);
    if (selected !== threadId) return;
    current().messages = full.messages || [];
    renderList(); renderConversation();
    for (const message of current()?.messages || []) {
      if (!isHuman(message.from) && !message.read_at) await api('read', {message_id: message.message_id});
    }
    await refresh();
  } catch (error) { toast(error.message); }
}

function openCompose() { $('newError').textContent = ''; $('composeDialog').showModal(); $('recipient').focus(); }
function showInfo(title, body) { $('infoTitle').textContent = title; $('infoBody').innerHTML = body; $('infoDialog').showModal(); }
function resetThreadActions() {
  $('threadActionMenu').hidden = false;
  $('threadActionContent').hidden = true;
  $('threadActionContent').innerHTML = '';
}
function closeThreadActions() {
  if ($('threadActionsDialog').open) $('threadActionsDialog').close();
  $('moreActions').setAttribute('aria-expanded', 'false');
  resetThreadActions();
}
function openThreadActions() {
  if (!current()) return;
  resetThreadActions();
  $('threadActionsDialog').showModal();
  $('moreActions').setAttribute('aria-expanded', 'true');
}
function showThreadAction(title, body, actionLabel, handler) {
  $('threadActionMenu').hidden = true;
  const content = $('threadActionContent');
  content.hidden = false;
  content.innerHTML = `<section class="thread-action-detail"><h3>${escapeHtml(title)}</h3><p>${body}</p><div class="action-dialog-buttons"><button type="button" class="secondary" id="actionBack">返回</button><button type="button" class="primary" id="actionConfirm">${escapeHtml(actionLabel)}</button></div><div class="quiet-note" id="actionStatus" role="status"></div></section>`;
  $('actionBack').onclick = resetThreadActions;
  $('actionConfirm').onclick = handler;
}
function openContinueAction() {
  const thread = current();
  if (!thread) return;
  const agentParticipants = (thread.participants || []).filter(participant => !isHuman(participant));
  const agentNames = agentParticipants.map(name).join('、');
  if (!agentParticipants.length) {
    showThreadAction('暂时不能继续', '这段对话还没有可联系的 Agent。请先邀请一个 Agent，或从“新建对话”开始。', '返回', resetThreadActions);
    $('actionConfirm').hidden = true;
    return;
  }
  showThreadAction('在新会话中继续', `这会在“${escapeHtml(thread.title)}”里留下一条请求，提醒 ${escapeHtml(agentNames)} 在新的会话读取这段对话并接着回复。`, '写入继续请求', async () => {
    const button = $('actionConfirm'); const status = $('actionStatus'); button.disabled = true; status.textContent = '正在写入…';
    try { await api('reply', {thread_id: selected, body: '请在新的 Agent 会话中继续阅读这段 Thread，带上必要上下文后接着回复。'}); closeThreadActions(); await refresh(); toast('已写入继续请求'); }
    catch (error) { status.textContent = error.message; button.disabled = false; }
  });
}
function openInviteAction() {
  const thread = current();
  if (!thread) return;
  $('threadActionMenu').hidden = true;
  const content = $('threadActionContent');
  content.hidden = false;
  content.innerHTML = `<section class="thread-action-detail"><h3>邀请其他 Agent</h3><p>邀请会作为一条新消息留在这段对话里。对方下次读取 Mail 时会看到邀请；此前的消息不会自动开放，请在说明里补充必要背景。</p><form id="inviteForm"><label class="field">邀请谁<input id="inviteAgent" required pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,79}" placeholder="例如：codex、reviewer"></label><label class="field">给他的说明<textarea id="inviteBody" required rows="3" placeholder="请加入这段对话，并补充需要知道的背景。"></textarea></label><div class="action-dialog-buttons"><button type="button" class="secondary" id="inviteBack">返回</button><button type="submit" class="primary">发送邀请</button></div><div class="quiet-note" id="inviteStatus" role="status"></div></form></section>`;
  $('inviteBack').onclick = resetThreadActions;
  $('inviteForm').onsubmit = async event => {
    event.preventDefault();
    const button = event.submitter; const status = $('inviteStatus'); button.disabled = true; status.textContent = '正在写入…';
    try { await api('invite', {thread_id: selected, to: $('inviteAgent').value.trim(), body: $('inviteBody').value.trim()}); closeThreadActions(); await refresh(); toast('邀请已写入这段对话'); }
    catch (error) { status.textContent = error.message; button.disabled = false; }
  };
  $('inviteAgent').focus();
}

function renderCommunication() {
  const agentCount = connection?.agents?.length || 0;
  const machineCount = connection?.machine_count || 0;
  $('workspacePage').innerHTML = `<header class="page-header"><div><span class="eyebrow">MAIL / 通信方式</span><h1>一段对话，四种继续方式。</h1><p>Mail 把消息写进知识库，让人和助手在不同会话、不同 Agent、不同电脑之间继续交流。</p></div><span class="page-badge">协议能力 · 实时状态见对话</span></header><section class="communication-intro"><div><span class="intro-symbol">↔</span><div><h2>你只需要继续说话。</h2><p>对话结束、换个 Agent 或换台电脑，Thread 仍是同一个上下文入口。</p></div></div><button class="primary" data-view="mail">打开对话</button></section><section class="communication-grid" aria-label="四种通信方式"><article class="communication-card"><span class="communication-icon">你</span><span class="pill available">可用</span><h2>你 ↔ Agent</h2><p>你发消息，目标 Agent 在自己的会话里读取并回复同一段 Thread。</p><small>真实写入 Mail Core</small></article><article class="communication-card"><span class="communication-icon">↳</span><span class="pill available">可用</span><h2>同一个 Agent，换个会话</h2><p>Session 只是一次运行；新的 Session 读取同一 Thread 的必要消息。</p><small>消息 + Session provenance</small></article><article class="communication-card"><span class="communication-icon">A↔A</span><span class="pill ${agentCount > 1 ? 'available' : 'pending'}">${agentCount > 1 ? `已发现 ${agentCount} 个 Agent` : '等待更多 Agent'}</span><h2>多个 Agent 一起讨论</h2><p>多个稳定的 Agent 身份可以共享同一 Thread，回复会按顺序保留。</p><small>当前观测：${agentCount} 个非 human Agent Session</small></article><article class="communication-card"><span class="communication-icon">⌂</span><span class="pill ${machineCount > 1 ? 'available' : 'pending'}">${machineCount > 1 ? `已记录 ${machineCount} 台机器` : '通过 Git 同步'}</span><h2>换一台电脑继续</h2><p>同步同一份 Mail 文件后，另一台机器继续读写；保存、同步、收到分别记录。</p><small>${escapeHtml(connection?.sync?.message || 'Git 是跨机器传输方式')}</small></article></section><section class="communication-proof"><h2>打开 Thread 时会看到什么？</h2><div class="proof-grid"><p><b>参与者</b><span>这段对话是谁和谁在交流。</span></p><p><b>可跨会话继续</b><span>Thread 不因 Session 结束而消失。</span></p><p><b>来源与回执</b><span>详情里展开 Session、机器和已读记录。</span></p><p><b>跨机器状态</b><span>只有真实记录到不同机器来源时，才显示已发生跨机器通信。</span></p></div></section>`;
}

function renderAgents() {
  const agents = connection?.agents || [];
  const cards = agents.length ? agents.map(agent => `<article class="agent-card"><div class="card-top"><span class="avatar ${agent.online ? 'mint' : 'muted'}">${escapeHtml(name(agent.agent_id).slice(0, 1).toUpperCase())}</span><span class="pill ${agent.online ? 'available' : ''}">${agent.online ? '在线' : '最近出现'}</span></div><h2>${escapeHtml(name(agent.agent_id))}</h2><p>${agent.online ? '这个 Agent 最近注册了 Session，可以读取自己的 Mail。' : '这个 Agent 的 Session 记录存在，但当前没有心跳。'}</p><dl><div><dt>Session</dt><dd>${agent.session_count}</dd></div><div><dt>机器</dt><dd>${agent.machine_ids.length}</dd></div><div><dt>最近活动</dt><dd>${escapeHtml(formatTime(agent.last_seen_at))}</dd></div></dl></article>`).join('') : '<div class="empty"><h3>还没有发现 Agent Session</h3><p>把连接请求交给目标 Agent；它安装 Skill 并启动后会出现在这里。</p></div>';
  const firstAgent = agents[0] ? name(agents[0].agent_id) : '';
  $('workspacePage').innerHTML = `<header class="page-header"><div><span class="eyebrow">我的协作空间 / 连接助手</span><h1>让 Agent 帮你接入。</h1><p>你只需写清想怎么协作；目标 Agent 会查找自己的 Skills、安装 oks-mail，并在下一次会话里验证连接。</p></div><span class="page-badge">${connection ? `${agents.length} 个 Agent · ${connection.sessions.length} 个 Session` : '正在读取状态…'}</span></header><section class="context-flow"><div class="context-flow-head"><div><span class="eyebrow">第一步 · 写下需求</span><h2>告诉 Agent 你想怎么协作。</h2><p>这会写入一封真实 Mail。Agent 读取后负责查找和配置，不需要你猜目录或复制命令。</p></div></div><form id="connectionRequestForm" class="connection-request-form"><label class="field">目标 Agent<input id="requestAgent" required pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,79}" value="${escapeHtml(firstAgent)}" placeholder="例如：claude、codex、reviewer"><small>填写稳定的 Agent 名称；它下次读取 Mail 时会看到请求。</small></label><label class="field">我想怎么协作<textarea id="requestBody" required rows="4" maxlength="12000" placeholder="例如：请帮我接入 OKS Mail，以后每次新会话都能继续这段对话，并告诉我连接是否成功。"></textarea></label><div class="form-actions"><button class="primary" type="submit">发送给 Agent，开始连接</button><button class="secondary" type="button" id="copyRequest">复制连接请求</button></div><div id="requestStatus" class="quiet-note" role="status"></div></form></section><details class="advanced-setup"><summary>如果你就在这台电脑上，可直接安装（高级）</summary><p>这一步只写入目标 Agent 的 Skills 目录，不启动 Agent；启动后它会自行注册 Session。</p><form id="setupForm" class="setup-form"><label class="field">Agent 名称<input id="setupAgent" required pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,79}" placeholder="例如：claude、codex、reviewer"></label><label class="field">Skills 目录<input id="setupSkillsDir" required placeholder="例如：C:\\Users\\me\\project\\.agents\\skills"><small>只写入该目录下的 oks-mail，不覆盖已有不同内容。</small></label><button class="primary" type="submit">安装 oks-mail Skill</button><div id="setupStatus" class="quiet-note" role="status"></div></form></details><section class="agent-grid" aria-label="已发现的 Agent">${cards}</section><section class="connection-guide"><h2>换一台电脑继续</h2><p>每台机器在自己的 clone 中安装绑定；通过 Git 同步 Mail 文件。此页面只显示文件中已有的机器来源，不会替你 push、pull 或唤醒远端 Agent。</p><p class="quiet-note">当前机器：${escapeHtml(connection?.current_machine_id || '读取中')} · 知识库：${escapeHtml(connection?.knowledge_base || '')}</p></section>`;
  $('connectionRequestForm').onsubmit = async event => {
    event.preventDefault();
    const button = event.submitter; const status = $('requestStatus'); const target = $('requestAgent').value.trim(); const request = $('requestBody').value.trim(); button.disabled = true; status.textContent = '正在写入连接请求…';
    try { const result = await api('send', {to: target, title: '请帮我连接 OKS Mail', body: `请按 oks-mail Skill 处理这份连接请求。\n\n用户需求：\n${request}\n\n完成后请回复：是否已安装、绑定了哪个知识库、下一次 Session 如何继续。`}); status.textContent = `已写入 Thread ${result.thread_id}。${target.replace(/^@/, '')} 下次读取 Mail 后会处理。`; $('requestBody').value = ''; }
    catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
  };
  $('copyRequest').onclick = async () => {
    const target = $('requestAgent').value.trim() || '目标 Agent'; const request = $('requestBody').value.trim() || '请帮我连接 OKS Mail，并验证下一次 Session 是否能继续对话。'; const text = `请帮我连接 OKS Mail。目标 Agent：${target}\n\n我的需求：\n${request}\n\n请按 oks-mail Skill 查找、安装并验证连接。`;
    try { await navigator.clipboard.writeText(text); toast('连接请求已复制'); } catch { toast('复制失败，请手动复制需求'); }
  };
  $('setupForm').onsubmit = async event => {
    event.preventDefault();
    const button = event.submitter; const status = $('setupStatus'); button.disabled = true; status.textContent = '正在写入 Skill…';
    try { const result = await api('setup', {agent: $('setupAgent').value.trim(), skills_dir: $('setupSkillsDir').value.trim()}); status.textContent = `已安装到 ${result.path}。请重启目标 Agent，等它注册 Session 后再刷新。`; $('setupForm').reset(); await refreshConnection(); }
    catch (error) { status.textContent = error.message; } finally { button.disabled = false; }
  };
}

function renderMemory() {
  $('workspacePage').innerHTML = `<header class="page-header"><div><span class="eyebrow">我的协作空间 / 记忆</span><h1>记忆由知识库管理。</h1><p>Mail 负责留下通信上下文；Agent 使用 <code>oks recall</code> 查找与当前问题相关的记忆。</p></div><span class="page-badge">非 Mail 数据</span></header><section class="memory-intro"><span class="intro-symbol">✦</span><div><h2>保存、召回、注入是三件事。</h2><p>本页面不伪造记忆卡片。要查看真实内容，请让 Agent 使用 recall/query Skill；相关上下文会在它的 Session 中注入。</p></div></section><div class="quiet-note">Mail 不会自动把聊天变成记忆，也不会把全部历史塞进每次回答。真实的记忆内容和注入记录以知识库与 Agent 的执行记录为准。</div>`;
}

async function refreshConnection() {
  connection = await api('status');
  if (workspaceView === 'communication') renderCommunication();
  if (workspaceView === 'agents') renderAgents();
}

function switchWorkspace(view) {
  workspaceView = view;
  document.body.dataset.view = view;
  $('workspacePage').hidden = view === 'mail';
  $('inbox')?.classList.toggle('hidden', view !== 'mail');
  document.querySelector('.inbox').hidden = view !== 'mail';
  $('conversation').hidden = view !== 'mail';
  $('detailPanel').hidden = true;
  document.querySelectorAll('[data-view]').forEach(button => {
    const active = button.dataset.view === view;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  document.title = `OKS Studio · ${{mail:'对话', communication:'通信方式', agents:'连接', memory:'记忆'}[view] || '对话'}`;
  if (view === 'communication') renderCommunication();
  if (view === 'agents') renderAgents();
  if (view === 'memory') renderMemory();
}

$('new').onclick = openCompose; $('mobileNew').onclick = openCompose;
$('refresh').onclick = async () => { $('refresh').disabled = true; try { await refresh(); await refreshConnection(); toast('已刷新本地 Mail 状态'); } catch (error) { toast(error.message); } finally { $('refresh').disabled = false; } };
$('search').oninput = renderList;
$('reply').oninput = () => { drafts[selected] = $('reply').value; };
$('replyForm').onsubmit = async event => {
  event.preventDefault(); const body = $('reply').value.trim();
  if (!selected) { $('replyError').textContent = '请先选择一段对话'; return; }
  if (!body) { $('replyError').textContent = '回复内容不能为空'; $('reply').focus(); return; }
  $('replyError').textContent = ''; $('send').disabled = true;
  try { await api('reply', {thread_id:selected, body}); drafts[selected] = ''; await refresh(); toast('回复已写入 Mail'); } catch (error) { $('replyError').textContent = error.message; } finally { $('send').disabled = false; }
};
$('newForm').onsubmit = async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { const result = await api('send', {title:$('newTitle').value.trim(), body:$('newBody').value.trim(), to:$('recipient').value.trim()}); $('composeDialog').close(); $('newForm').reset(); selected = result.thread_id; document.body.classList.add('reading'); await refresh(); toast('消息已写入 Mail，等待对方 Session 读取'); } catch (error) { $('newError').textContent = error.message; } finally { button.disabled = false; }
};
async function updateArchive(action) {
  if (!selected) return;
  const button = action === 'archive' ? $('archive') : $('unarchive');
  button.disabled = true;
  try {
    await api(action, {thread_id:selected});
    closeThreadActions();
    if (action === 'archive') selected = '';
    else filter = 'all';
    await refresh();
    toast(action === 'archive' ? '已归档' : '已取消归档');
  } catch (error) { toast(error.message); } finally { button.disabled = false; }
}
$('archive').onclick = () => updateArchive('archive');
$('unarchive').onclick = () => updateArchive('unarchive');
function openDetailsPanel() {
  const thread = current();
  if (!thread) return;
  const machines = threadMachines(thread);
  const syncState = machines.size > 1 ? `跨机器已发生：消息记录了 ${machines.size} 台设备的来源。` : '尚无跨机器记录：目前只看到一台或未知设备来源。';
  $('detailContent').innerHTML = `<h4>参与者</h4><p>${escapeHtml((thread.participants || []).map(name).join(' · '))}</p><h4>跨机器状态</h4><p>${escapeHtml(syncState)}</p><p class="quiet-note">${escapeHtml(connection?.sync?.message || 'Mail Core 只记录消息来源，不会自动判断 Git 是否已同步。')}</p><h4>来源与回执</h4><details open><summary>展开每条消息的来源</summary><p>Thread：${escapeHtml(thread.thread_id)}</p>${(thread.messages || []).map(message => `<p>${escapeHtml(name(message.from))} · ${senderKind(message).label} · Session ${escapeHtml(message.origin_session_id || '未记录')} · Machine ${escapeHtml(message.origin_machine_id || '未记录')}${message.read_at ? ' · 已读' : ''}</p>`).join('')}</details>`;
  closeThreadActions();
  $('detailPanel').hidden = false;
  $('details').setAttribute('aria-expanded', 'true');
  $('closeDetails').focus();
}
$('details').onclick = openDetailsPanel;
$('moreActions').onclick = openThreadActions;
$('threadActionsDialog').addEventListener('close', () => { $('moreActions').setAttribute('aria-expanded', 'false'); resetThreadActions(); });
$('closeDetails').onclick = () => { $('detailPanel').hidden = true; $('details').setAttribute('aria-expanded', 'false'); $('moreActions').focus(); };
document.addEventListener('keydown', event => { if (event.key === 'Escape' && !$('detailPanel').hidden) $('closeDetails').click(); });
document.addEventListener('click', event => { const button = event.target.closest('button'); if (!button) return; if (button.dataset.thread) choose(button.dataset.thread); if (button.dataset.filter) { filter = button.dataset.filter; renderList(); } if (button.dataset.view) switchWorkspace(button.dataset.view); if (button.dataset.create) openCompose(); if (button.dataset.threadAction === 'continue') openContinueAction(); if (button.dataset.threadAction === 'invite') openInviteAction(); if (button.dataset.threadAction === 'details') openDetailsPanel(); if (button.dataset.threadAction === 'archive') updateArchive('archive'); if (button.dataset.threadAction === 'unarchive') updateArchive('unarchive'); if (button.hasAttribute('data-close')) { const dialog = button.closest('dialog'); if (dialog?.id === 'threadActionsDialog') closeThreadActions(); else dialog?.close(); } });
$('back').onclick = () => document.body.classList.remove('reading');

switchWorkspace('mail'); renderList(); renderConversation();
refresh().catch(error => { loading = false; renderList(); $('runtimeText').textContent = `读取 Mail 失败：${error.message}`; toast(error.message); });
refreshConnection().catch(error => { $('runtimeText').textContent = `Mail 已连接，状态读取失败：${error.message}`; });
