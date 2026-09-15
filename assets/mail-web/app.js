const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let threads = [];
let selected = '';
let filter = 'all';
let drafts = {};
let loading = true;
let workspaceView = 'mail';
let connection = null;
let team = null;
let memory = null;
let members = null;
let memoryKindFilter = 'all';
let memoryAreaFilter = 'all';
let memoryTypeFilter = 'all';

const mobileNav = document.querySelector('.workspace-mobile');
mobileNav.innerHTML = document.querySelector('.workspace-nav').innerHTML;
mobileNav.querySelector('.workspace-nav-title')?.remove();

function isHuman(id) { return String(id || '').replace(/^@/, '').toLowerCase() === 'human'; }
function name(id) { return isHuman(id) ? '你' : String(id || '').replace(/^@/, '') === 'all' ? '全体成员' : String(id || 'unknown').replace(/^@/, ''); }
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
function recordKindLabel(value) {
  return ({message:'消息', handoff:'交接', result:'结果', blocked:'阻塞', note:'批注', knowledge_ref:'知识引用'})[value] || '消息';
}
const MAIL_INTENTS = {
  handoff: {record_kind:'handoff', delivery_reason:'handoff'},
  result: {record_kind:'result', delivery_reason:'direct'},
  blocked: {record_kind:'blocked', delivery_reason:'direct'},
  knowledge_ref: {record_kind:'knowledge_ref', delivery_reason:'review_request'},
  note: {record_kind:'note', delivery_reason:'mention'},
  message: {record_kind:'message', delivery_reason:'direct'},
};
function threadMachines(thread) {
  return new Set((thread?.messages || []).map(message => message.origin_machine_id).filter(machine => machine && machine !== 'unknown'));
}
function threadSessions(thread) {
  return new Set((thread?.messages || []).map(message => message.origin_session_id).filter(session => session && session !== 'unknown'));
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
  const endpoint = String(path || '').startsWith('/') ? path : `/api/mail/${path}`;
  const response = await fetch(endpoint, payload === undefined ? {cache:'no-store'} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  let value = {};
  try { value = await response.json(); } catch { /* keep the HTTP error useful */ }
  if (!response.ok) throw new Error(value.error || `请求失败（${response.status}）`);
  return value;
}

function conversationModes(thread) {
  const participants = (thread?.participants || []).filter(participant => !isHuman(participant));
  const machines = threadMachines(thread);
  const sessions = threadSessions(thread);
  const modes = [{label:'协作事实', detail:'正文只记录已经发生或明确提出的协作事实。', kind:'fact'}];
  if (participants.length > 1) modes.push({label:'多人参与', detail:'这段记录包含多个参与身份。', kind:'fact'});
  else if (participants.length === 1) modes.push({label:`参与者：${name(participants[0])}`, detail:'参与者是 provenance，不代表在线或可调用。', kind:'fact'});
  if (sessions.size > 1) modes.push({label:`${sessions.size} 个 Session 接力`, detail:'同一 Thread 由多个独立运行继续；Session 变化不代表任务已完成。', kind:'fact'});
  if (machines.size > 1) modes.push({label:`跨机器已发生（${machines.size} 台）`, detail:'这段记录了多台设备来源；Git 同步仍需由你或 Agent 执行。', kind:'fact'});
  else modes.push({label:'未发现跨机器记录', detail:'目前只看到一台或未知设备来源；Mail 不会自动判断 Git 是否已同步。', kind:'pending'});
  return modes;
}

function renderList() {
  const query = $('search').value.trim().toLowerCase();
  const rows = threads.filter(thread =>
    isVisibleThread(thread) &&
    [
      thread.title,
      ...(thread.participants || []),
      ...(thread.messages || []).flatMap(message => [
        message.title,
        message.body,
        message.from,
        ...(message.to || [])
      ])
    ].filter(Boolean).join(' ').toLowerCase().includes(query));
  $('total').textContent = threads.filter(thread => thread.state !== 'archived').length;
  $('unread').textContent = threads.filter(thread => thread.unread_count > 0 && thread.state !== 'archived').length;
  $('listTitle').textContent = {all:'协作记录', unread:'未读记录', archived:'已归档记录'}[filter];
  document.querySelectorAll('[data-filter]').forEach(button => {
    const active = button.dataset.filter === filter;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  if (loading) { $('threadList').innerHTML = '<div class="empty" role="status">正在读取邮箱…</div>'; return; }
  if (!rows.length) { $('threadList').innerHTML = '<div class="empty"><h3>这里还没有协作事项</h3><p>从一个明确动作开始；后续 Session 会在同一 Thread 里接着走。</p><div class="empty-actions"><button class="primary" data-create-intent="handoff">交接工作</button><button class="secondary" data-create-intent="knowledge_ref">请求审核</button><button class="secondary" data-create-intent="result">报告结果</button><button class="secondary" data-create-intent="blocked">报告阻塞</button></div></div>'; return; }
  $('threadList').innerHTML = rows.map(thread => {
    const people = (thread.participants || []).filter(participant => !isHuman(participant));
    const latest = thread.messages?.at(-1) || {from: people[0] || 'unknown', sender_kind: people.length ? 'agent' : 'human'};
    const sessions = threadSessions(thread);
    const mode = people.length > 1 ? '多人记录' : people.length === 1 ? '协作事实' : '我的记录';
    const sessionTag = sessions.size > 1 ? `<span class="tag">${sessions.size} 个 Session</span>` : '';
    return `<button class="thread ${thread.thread_id === selected ? 'selected' : ''}" data-thread="${escapeHtml(thread.thread_id)}"><div class="thread-top">${avatar(latest.from)}<b class="thread-sender">${senderLabel(latest)}</b><time>${escapeHtml(formatTime(thread.last_at))}</time></div><h3>${escapeHtml(thread.title)}</h3><p>${escapeHtml(latest.body || '')}</p><span class="tag">${escapeHtml(mode)}</span>${sessionTag}${thread.unread_count ? `<span class="tag unread-tag">${thread.unread_count} 条未读</span>` : ''}</button>`;
  }).join('');
}

function renderConversation() {
  const thread = current();
  const box = $('messages');
  // The conversation panel is hidden while the list view is active. Do not
  // write a thread sentinel or calculate a scroll position while it has no
  // layout; otherwise the first real mobile open can be mistaken for a
  // re-render of the same thread and remain at the top.
  const hasLayout = box.clientHeight > 0;
  const previousThread = hasLayout ? (box.dataset.thread || '') : '';
  const wasNearBottom = hasLayout && box.scrollHeight - box.scrollTop - box.clientHeight < 80;
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
  $('messages').innerHTML = thread ? (thread.messages || []).map(message => `<article class="message ${isHuman(message.from) ? 'mine' : ''}">${avatar(message.from)}<div class="message-content"><div class="message-meta"><b class="message-sender">${senderLabel(message)}</b><span class="record-kind">${escapeHtml(recordKindLabel(message.record_kind))}</span><time>${escapeHtml(formatTime(message.timestamp))}</time></div><div class="message-body">${escapeHtml(message.body)}</div>${(message.evidence_refs || []).length ? `<div class="evidence"><span>Evidence · ${escapeHtml(message.evidence_refs.map(ref => ref.type || 'ref').join('、'))}</span></div>` : ''}</div></article>`).join('') : '<div class="empty"><h3>重要的协作事实，都留在这里</h3><p>从左侧打开记录，查看 Thread、provenance 和 Evidence。</p></div>';
  $('replyTo').textContent = thread ? '添加到这段记录' : '';
  if (thread) window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    if (previousThread !== thread.thread_id || wasNearBottom) box.scrollTop = box.scrollHeight;
    if (box.clientHeight > 0) box.dataset.thread = thread.thread_id;
  }));
}

async function refresh() {
  const previouslySelected = current();
  const snapshot = await api('snapshot');
  threads = snapshot.threads || [];
  if (previouslySelected && !threads.some(thread => thread.thread_id === selected)) threads.push(previouslySelected);
  loading = false;
  if (!threads.some(thread => thread.thread_id === selected && isVisibleThread(thread))) selected = threads.find(isVisibleThread)?.thread_id || '';
  if (selected) current().messages = (await api(`thread?id=${encodeURIComponent(selected)}`)).messages || [];
  renderList(); renderConversation();
  $('syncLabel').textContent = snapshot.truncated ? '显示最近 100 段；更早记录由 Agent 查阅' : '当前知识库 · 已更新';
  $('runtimeText').textContent = '只保存明确发送到 Mail 的消息，不自动录制日常 Agent 聊天';
}

async function choose(threadId) {
  switchWorkspace('mail');
  selected = threadId;
  document.body.classList.add('reading');
  $('detailPanel').hidden = true;
  try {
    const full = await api(`thread?id=${encodeURIComponent(threadId)}`);
    if (selected !== threadId) return;
    if (!current()) threads.push({thread_id:threadId, title:full.title, state:full.state,
      participants:[...new Set((full.messages || []).flatMap(message => [message.from, ...(message.to || [])]))],
      unread_count:0, last_at:full.messages?.at(-1)?.timestamp, messages:full.messages || []});
    filter = full.state === 'archived' ? 'archived' : 'all';
    current().messages = full.messages || [];
    renderList(); renderConversation();
    for (const message of current()?.messages || []) {
      if (!isHuman(message.from) && !message.read_at) await api('read', {message_id: message.message_id});
    }
    await refresh();
  } catch (error) { toast(error.message); }
}

function openCompose(intent = 'handoff', context = {}) {
  $('newError').textContent = '';
  $('newIntent').value = intent;
  if (context.evidencePath) $('newEvidencePath').value = context.evidencePath;
  if (context.title) $('newTitle').value = context.title;
  if (context.body) $('newBody').value = context.body;
  $('composeDialog').showModal(); $('recipient').focus();
}
function renderRecipientHints() {
  const ids = new Set();
  for (const profile of (members?.profiles || [])) {
    if (profile.kind === 'assistant' && profile.id) ids.add(String(profile.id).replace(/^@/, ''));
  }
  for (const agent of (connection?.agents || [])) {
    const id = String(agent.agent_id || '').replace(/^@/, '');
    if (id && !isHuman(id) && id.toLowerCase() !== 'all') ids.add(id);
  }
  const datalist = $('agentChoices');
  if (datalist) datalist.innerHTML = [...ids].sort((a, b) => a.localeCompare(b)).map(id => `<option value="${escapeHtml(id)}"></option>`).join('');
}
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
function deliverySummary(message) {
  const rows = message.deliveries || [];
  if (!rows.length) return '<p class="receipt">已保存 · 暂无收件回执</p>';
  return `<div class="delivery-summary">${rows.map(recipient => {
    const sessions = recipient.sessions || [];
    let status = '已保存 · 等待对方读取';
    if (recipient.agent_id === '@all') status = '已保存 · 面向全体';
    if (sessions.some(session => session.injected_at || session.delivered_at)) status = '已送入会话 · 等待确认';
    if (recipient.read_at) status = '已标记已读';
    if (sessions.some(session => session.acknowledged_at)) status = '已确认收到';
    const reply = current()?.messages?.find(item => item.reply_to === message.message_id && name(item.from) === name(recipient.agent_id));
    if (reply) status = '已回复';
    return `<p class="receipt">${escapeHtml(name(recipient.agent_id))} · ${status}</p>`;
  }).join('')}</div>`;
}

function threadTimeline(thread) {
  const events = [];
  const add = (message, type, timestamp, actor, sessionId = '', machineId = '') => {
    if (!timestamp) return;
    events.push({type, timestamp, actor, sessionId, machineId, messageId: message.message_id});
  };
  for (const message of thread?.messages || []) {
    add(message, message.reply_to ? 'reply' : 'message', message.timestamp, message.from, message.origin_session_id, message.origin_machine_id);
    for (const recipient of message.deliveries || []) {
      add(message, 'read', recipient.read_at, recipient.agent_id);
      for (const session of recipient.sessions || []) {
        add(message, 'presented', session.delivered_at, recipient.agent_id, session.session_id, session.machine_id);
        add(message, 'injected', session.injected_at, recipient.agent_id, session.session_id, session.machine_id);
        add(message, 'acknowledged', session.acknowledged_at, recipient.agent_id, session.session_id, session.machine_id);
      }
    }
  }
  return events.sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)) || String(a.messageId).localeCompare(String(b.messageId)));
}

function timelineLabel(type) {
  return ({message:'发送', reply:'回复', presented:'呈现给 Session', injected:'注入会话', read:'标记已读', acknowledged:'确认收到'})[type] || type;
}

function appendAgentGuide() {
  const guide = document.createElement('section');
  guide.className = 'connection-guide';
  guide.setAttribute('aria-label', 'Agent 接入与 Git 同步');
  const teamStateLabel = {clean:'已同步', dirty:'有本机团队文件待同步', no_remote:'还没有团队远端', not_git:'尚未建立团队 Git', wrong_root:'路径不在知识库根目录'};
  const teamState = team?.state || 'not_git';
  const teamMessage = team?.message || '正在读取团队 Git 状态。';
  const canSync = Boolean(team?.remote) && !['wrong_root', 'not_git', 'no_remote'].includes(teamState);
  const teamAction = canSync
    ? '<button class="primary" type="button" data-team-sync>一键同步团队资料</button>'
    : '';
  guide.innerHTML = '<h2>怎么接入 Agent</h2>' +
    '<p>不用再安装 Skill：<code>oks init</code> 已把 <code>oks-mail</code> 随知识库放进 Agent 目录。Agent 被调用时检查同一个 Mail 文件；不会后台轮询、远程唤醒或假装在线。</p>' +
    '<div class="guide-steps">' +
      '<article><b>01 · 准备同一个知识库</b><h3>每台机器各自 clone</h3><p>团队共享一个 Git 仓库；每台机器都使用它自己的本地 clone。</p></article>' +
      '<article><b>02 · 身份自动保留</b><h3>Agent 直接读 Mail</h3><p>在这个知识库里运行 <code>oks mail inbox</code> 或 <code>oks mail snapshot</code> 即可。每个 Agent 使用稳定 ID，读取和回复都会留下 provenance。</p></article>' +
      '<article><b>03 · 继续同一段协作</b><h3>检查收件箱或 Thread</h3><pre><code>oks mail snapshot&#10;oks mail thread THREAD_ID</code></pre><p>回复时使用同一个 Thread；读取、回复、完成任务是三个不同事实。只有 Agent 在知识库外运行时，才需要额外的本机 binding。</p></article>' +
    '</div>' +
    `<section class="team-sync-card" aria-label="小团队 Git 同步"><div><span class="eyebrow">小团队 Git 协作</span><h3>${escapeHtml(teamStateLabel[teamState] || '团队 Git 状态')}</h3><p>${escapeHtml(teamMessage)}</p><p class="quiet-note">流程：整理共享文件 → 提交 → 拉取并合并 → 推送。只同步 mail、raw、drafts、wiki、profiles，不碰各机器的 binding。</p></div>${teamAction}</section>` +
    '<details class="advanced-setup"><summary>查看一次性准备与命令行兜底</summary><p>负责人只需把这个知识库建立为 Git 仓库并配置一个 origin 远端；其他成员 clone 同一仓库即可。之后优先点击上面的“一键同步团队资料”。</p><pre><code>oks team init &lt;知识库路径&gt;&#10;git remote add origin &lt;团队仓库地址&gt;&#10;oks team sync --push</code></pre><p>不要提交各机器自己的 <code>binding.json</code>。Git 只负责交换文件，不代表对方已读、在线或立即执行。</p></details>';
  $('workspacePage').appendChild(guide);
}

function renderAgents() {
  const agents = connection?.agents || [];
  const statusLabel = {observed:'已观察', verified:'Mail 已验证', unverified:'未验证'};
  const profiles = (members?.profiles || []).filter(profile => profile.kind === 'assistant');
  const profileIds = new Set(profiles.map(profile => String(profile.id).replace(/^@/, '').toLowerCase()));
  const observedOnly = agents.filter(agent => !profileIds.has(String(agent.agent_id).replace(/^@/, '').toLowerCase()));
  const profileCard = profile => {
    const agent = agents.find(item => String(item.agent_id).replace(/^@/, '').toLowerCase() === String(profile.id).replace(/^@/, '').toLowerCase());
    const verification = agent?.verification_status || 'unverified';
    const profileStatus = profile.status || 'active';
    const profileStatusLabel = {active:'已有共享档案', proposed:'待确认档案', retired:'已退役档案'}[profileStatus] || profileStatus;
    const provenance = agent ? `<dl><div><dt>Session</dt><dd>${agent.session_count}</dd></div><div><dt>机器</dt><dd>${agent.machine_ids.length}</dd></div><div><dt>最近观察</dt><dd>${escapeHtml(formatTime(agent.last_observed_at))}</dd></div></dl>` : '<p class="quiet-note">已有共享档案，尚未观察到 Session 或 Mail provenance。</p>';
    const evidence = agent?.verification_evidence ? `<small>证据：${escapeHtml(agent.verification_evidence.evidence)} · ${escapeHtml(agent.verification_evidence.message_id || '')}</small>` : '<small>尚无 Mail ack 或回复证据</small>';
    return `<article class="agent-card"><div class="card-top"><span class="avatar mint">${escapeHtml(profile.title.slice(0, 1).toUpperCase())}</span><span class="pill ${profileStatus === 'active' ? 'verified' : 'pending'}">${escapeHtml(profileStatusLabel)}</span></div><h2>${escapeHtml(profile.title)}</h2><p class="member-id">@${escapeHtml(profile.id)}</p><p class="member-role">${escapeHtml(profile.role || '职责尚未填写')}</p>${profile.summary ? `<p>${escapeHtml(profile.summary)}</p>` : ''}${profile.scope ? `<small>范围：${escapeHtml(profile.scope)}</small>` : ''}${provenance}${evidence}</article>`;
  };
  const observedCard = agent => {
    const id = String(agent.agent_id).replace(/^@/, '');
    const verification = agent.verification_status || 'observed';
    const evidence = agent.verification_evidence ? `<small>证据：${escapeHtml(agent.verification_evidence.evidence)} · ${escapeHtml(agent.verification_evidence.message_id || '')}</small>` : '<small>尚无 Mail ack 或回复证据</small>';
    return `<article class="agent-card observed-only"><div class="card-top"><span class="avatar mint">${escapeHtml(name(id).slice(0, 1).toUpperCase())}</span><span class="pill ${verification === 'verified' ? 'verified' : ''}">${statusLabel[verification] || '已观察来源'}</span></div><h2>${escapeHtml(name(id))}</h2><p class="member-id">@${escapeHtml(id)}</p><p>这里只证明身份出现在 Session 或 Mail provenance 中，当前还没有共享角色档案。</p><dl><div><dt>Session</dt><dd>${agent.session_count}</dd></div><div><dt>机器</dt><dd>${agent.machine_ids.length}</dd></div><div><dt>最近观察</dt><dd>${escapeHtml(formatTime(agent.last_observed_at))}</dd></div></dl>${evidence}<button class="secondary member-request-button" type="button" data-member-add="assistant" data-member-agent="${escapeHtml(id)}">提交建档申请</button></article>`;
  };
  const profileRows = profiles.map(profileCard).join('') || '<div class="empty member-empty"><h3>还没有共享 Agent 档案</h3><p>观察到的身份不会自动变成团队事实；提交建档申请后，由负责 Agent 建立 profiles/agents/&lt;id&gt;.md。</p><button class="primary" type="button" data-member-add="assistant">添加助手</button></div>';
  const observedRows = observedOnly.map(observedCard).join('') || '<div class="empty member-empty"><p>当前没有额外的仅来源成员。</p></div>';
  const teamProfile = (members?.profiles || []).find(profile => profile.kind === 'team');
  const teamIntro = teamProfile ? `<section class="team-context"><span class="eyebrow">团队档案</span><h2>${escapeHtml(teamProfile.title)}</h2><p>${escapeHtml(teamProfile.summary)}</p></section>` : '';
  const totalMembers = profiles.length + observedOnly.length;
  $('workspacePage').innerHTML = `<header class="page-header"><div><span class="eyebrow">协作记录 / provenance</span><h1>成员与来源</h1><p>先看共享角色档案，再看仅有来源记录。出现过不等于在线、可达或可调用。</p></div><div class="page-header-actions"><span class="page-badge">${connection ? `${totalMembers} 个成员 · ${connection.sessions.length} 个观察到的 Session` : '正在读取状态…'}</span><button class="primary" type="button" data-member-add="assistant">添加助手</button><button class="secondary" type="button" data-member-add="member">添加成员档案</button></div></header>${teamIntro}<section class="member-section"><div class="member-section-heading"><div><span class="eyebrow">共享档案</span><h2>已有成员档案 <span>${profiles.length}</span></h2><p>来自 <code>profiles/agents/*.md</code>，描述职责与范围，可随知识库 Git 共享。</p></div></div><section class="agent-grid" aria-label="已有成员档案">${profileRows}</section></section><section class="member-section observed-section"><div class="member-section-heading"><div><span class="eyebrow">provenance</span><h2>仅观察到来源 <span>${observedOnly.length}</span></h2><p>来自真实 Mail、Session 或 Machine 记录；没有档案的身份不会自动获得职责和权限。</p></div></div><section class="agent-grid" aria-label="仅观察到来源">${observedRows}</section></section><section class="connection-guide"><h2>状态说明</h2><p>已观察：出现过真实 Agent、Session 或 Machine provenance。Mail 已验证：至少有一次发送后呈现并 ack，或在同一 Thread 中产生回复。Host 执行能力需要独立 Adapter 证据，本页面不推断。</p><p class="quiet-note">当前机器：${escapeHtml(connection?.current_machine_id || '读取中')} · Git 只负责文件传输，不代表实时同步。</p></section>`;
}

async function openMemoryItem(path) {
  if (!path) return;
  try {
    const item = await api(`/api/memory/item?path=${encodeURIComponent(path)}`);
    $('detailTitle').textContent = item.title || '知识详情';
    $('detailContent').innerHTML = `<p class="memory-detail-summary">${escapeHtml(item.summary || '')}</p><p class="quiet-note">${escapeHtml(item.kind_label || '')} · ${escapeHtml(item.path || '')} · ${escapeHtml(formatTime(item.updated_at))}</p><div class="memory-detail-actions"><button class="primary" type="button" data-memory-collab-path="${escapeHtml(item.path || '')}" data-memory-collab-title="${escapeHtml(item.title || '')}">请求成员审核</button><span class="quiet-note">以知识引用方式写入同一协作记录</span></div><h4>知识正文</h4><pre class="memory-detail-body">${escapeHtml(item.body || '')}${item.truncated ? '\n\n[正文过长，详情只显示前 12000 个字符]' : ''}</pre><details><summary>查看元数据</summary><pre class="memory-detail-meta">${escapeHtml(JSON.stringify(item.metadata || {}, null, 2))}</pre></details>`;
    $('detailPanel').hidden = false;
    $('detailPanel').setAttribute('aria-label', '知识详情');
    $('details').setAttribute('aria-expanded', 'false');
    $('closeDetails').focus();
  } catch (error) { toast(`知识详情读取失败：${error.message}`); }
}

async function renderMemory() {
  if (!memory) {
    try { memory = await api('/api/memory'); } catch (error) { $('workspacePage').innerHTML = `<div class="empty" role="alert"><h3>记忆页暂时读不到</h3><p>${escapeHtml(error.message)}</p><p>请确认 Mail 服务已重启到当前版本；记忆页只读，不会修改知识库。</p><button class="primary" data-refresh-memory>重试</button></div>`; return; }
  }
  const counts = memory.counts || {};
  const allRecent = memory.recent || [];
  const filtered = allRecent.filter(item => (memoryKindFilter === 'all' || item.kind === memoryKindFilter) && (memoryAreaFilter === 'all' || item.area === memoryAreaFilter) && (memoryTypeFilter === 'all' || item.type === memoryTypeFilter));
  const facets = memory.facets || {areas: {}, types: {}};
  const areaOptions = Object.keys(facets.areas || {}).sort((a, b) => a.localeCompare(b, 'zh-CN'));
  const typeOptions = Object.keys(facets.types || {}).sort((a, b) => a.localeCompare(b, 'zh-CN'));
  const card = item => `<button class="memory-card recent-memory" type="button" data-memory-path="${escapeHtml(item.path)}" aria-label="打开 ${escapeHtml(item.title || '知识详情')}"><div class="card-top"><span class="memory-icon">${item.kind === 'wiki' ? 'W' : 'C'}</span><span class="pill ${item.kind === 'wiki' ? 'verified' : 'pending'}">${escapeHtml(item.kind_label || (item.kind === 'wiki' ? '已审核 Wiki' : 'Candidate 候选'))}</span></div><h3>${escapeHtml(item.title || '未命名知识')}</h3><p>${escapeHtml(item.summary || '打开查看详情')}</p><div class="memory-card-meta"><span>${escapeHtml(item.area || '未分类')}</span><span>${escapeHtml(item.type || '')}</span><span>${escapeHtml(item.status_label || item.status || '')}</span></div><div class="card-source"><span>${escapeHtml(formatTime(item.updated_at))}</span><span>${escapeHtml(item.timestamp_source === 'file_mtime' ? '文件时间' : '知识记录时间')}</span></div></button>`;
  const groups = [...new Set(filtered.map(item => item.area || '未分类'))].sort((a, b) => a.localeCompare(b, 'zh-CN')).map(area => `<section class="memory-group"><h3>${escapeHtml(area)}</h3><div class="memory-grid recent-memory-grid">${filtered.filter(item => (item.area || '未分类') === area).map(card).join('')}</div></section>`).join('') || '<div class="empty"><p>当前筛选下暂无知识；换一个分类或刷新。</p></div>';
  const excludedNote = counts.excluded ? ` · 已隐藏 ${counts.excluded} 条已归档/丢弃资产` : '';
  $('workspacePage').innerHTML = `<header class="page-header"><div><span class="eyebrow">知识复利主线</span><h1>记忆</h1><p>Raw 保留来源，Candidate 等待人审，Wiki 才是可复用的长期知识。这里展示最近收录或更新的知识，按领域分组，点开可看标题、摘要和正文。</p></div><span class="page-badge">只读投影</span></header><section class="memory-intro"><div><span class="intro-symbol">◇</span><div><h2>显式反馈，推动下一次 Candidate。</h2><p>Recall 之后只有明确的过时、缺条件、结果不符或新经验反馈，才进入下一轮提炼。</p></div></div></section><section class="context-flow"><div class="context-flow-head"><div><span class="eyebrow">生命周期</span><h2>raw → candidate → human review → wiki → recall</h2><p>当前页面只展示文件事实，不执行 ingest、promote 或 Agent 调度。</p></div></div><div class="context-steps">${(memory.lifecycle || []).map((step, index) => `<div class="context-step"><span>0${index + 1}</span><b>${escapeHtml(step)}</b><p>${step === 'explicit_feedback' ? '明确反馈后再生成 Candidate' : '真实文件与证据投影'}</p></div>`).join('')}</div></section><section class="section-heading"><h2>当前资产 <span>可复用与待审核统计</span></h2></section><div class="memory-grid"><article class="memory-card"><div class="card-top"><span class="memory-icon">R</span><span class="pill">Raw</span></div><h3>${counts.raw || 0} 份来源</h3><p>原始材料与机械提取结果，不直接等同于知识。</p></article><article class="memory-card"><div class="card-top"><span class="memory-icon">C</span><span class="pill pending">Candidate</span></div><h3>${counts.drafts || 0} 份待审核候选</h3><p>等待人审、修改、接受或拒绝的中间产物。</p></article><article class="memory-card"><div class="card-top"><span class="memory-icon">W</span><span class="pill verified">Wiki</span></div><h3>${counts.wiki || 0} 页可复用知识</h3><p>通过审核、可在后续任务中被 Recall 的长期资产。</p></article></div><section class="recent-memory-section"><div class="section-heading"><h2>最近收录知识 <span>最近 12 条 · 按知识记录时间排序${excludedNote}</span></h2></div><div class="memory-toolbar"><div class="memory-kind-tabs" role="group" aria-label="知识类型"><button type="button" data-memory-kind="all" class="${memoryKindFilter === 'all' ? 'active' : ''}">全部</button><button type="button" data-memory-kind="wiki" class="${memoryKindFilter === 'wiki' ? 'active' : ''}">已审核 Wiki</button><button type="button" data-memory-kind="candidate" class="${memoryKindFilter === 'candidate' ? 'active' : ''}">Candidate</button></div><label class="memory-area-filter">领域<select id="memoryArea"><option value="all">全部领域</option>${areaOptions.map(area => `<option value="${escapeHtml(area)}" ${area === memoryAreaFilter ? 'selected' : ''}>${escapeHtml(area)}（${facets.areas[area]}）</option>`).join('')}</select></label><label class="memory-area-filter">类型<select id="memoryType"><option value="all">全部类型</option>${typeOptions.map(type => `<option value="${escapeHtml(type)}" ${type === memoryTypeFilter ? 'selected' : ''}>${escapeHtml(type)}（${facets.types[type]}）</option>`).join('')}</select></label></div><div class="memory-groups">${groups}</div></section>`;
  $('memoryArea').onchange = event => { memoryAreaFilter = event.target.value; renderMemory(); };
  $('memoryType').onchange = event => { memoryTypeFilter = event.target.value; renderMemory(); };
}

function openMemberDialog(kind = 'assistant', suggestedId = '') {
  const dialog = $('memberDialog');
  $('memberKind').value = kind;
  $('memberDialogTitle').textContent = kind === 'member' ? '添加成员档案' : '添加助手';
  $('memberForm').reset();
  $('memberKind').value = kind;
  if (suggestedId) {
    $('memberId').value = suggestedId.replace(/^@/, '');
    $('memberName').value = name(suggestedId);
  }
  $('memberError').textContent = '';
  dialog.showModal();
  $('memberController').focus();
}

async function refreshConnection() {
  connection = await api('status');
  try { team = await api('team'); } catch (error) { team = {state:'error', message:`团队同步状态读取失败：${error.message}`}; }
  try { members = await api('members'); } catch (error) { members = {profiles: []}; }

  renderRecipientHints();
  if (workspaceView === 'agents') { renderAgents(); appendAgentGuide(); }
  if (workspaceView === 'memory') renderMemory();
}

function switchWorkspace(view) {
  if (view !== workspaceView) $('workspacePage').scrollTop = 0;
  workspaceView = view;
  document.body.dataset.view = view;
  $('workspacePage').hidden = view === 'mail';
  document.querySelector('.inbox').hidden = view !== 'mail';
  $('conversation').hidden = view !== 'mail';
  $('detailPanel').hidden = true;
  document.querySelectorAll('.workspace-nav button[data-view], .workspace-mobile button[data-view]').forEach(button => {
    const active = button.dataset.view === view;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  document.title = `OKS Studio · ${{mail:'协作记录', memory:'记忆', agents:'成员与来源'}[view] || '知识工作台'}`;
  if (view === 'agents') { renderAgents(); appendAgentGuide(); }
  if (view === 'memory') renderMemory();
}

$('new').onclick = () => openCompose(); $('mobileNew').onclick = () => openCompose();
$('refresh').onclick = async () => { $('refresh').disabled = true; try { memory = null; await refresh(); await refreshConnection(); toast('已刷新本地知识与 Mail 状态'); } catch (error) { toast(error.message); } finally { $('refresh').disabled = false; } };
$('search').oninput = renderList;
$('reply').oninput = () => { drafts[selected] = $('reply').value; };
$('replyForm').onsubmit = async event => {
  event.preventDefault(); const body = $('reply').value.trim();
  if (!selected) { $('replyError').textContent = '请先选择一段对话'; return; }
  if (!body) { $('replyError').textContent = '回复内容不能为空'; $('reply').focus(); return; }
  $('replyError').textContent = ''; $('send').disabled = true;
  try { await api('reply', {thread_id:selected, body}); drafts[selected] = ''; await refresh(); toast('协作记录已追加，可在详情查看真实回执'); } catch (error) { $('replyError').textContent = error.message; } finally { $('send').disabled = false; }
};
$('newForm').onsubmit = async event => {
  event.preventDefault();
  // requestSubmit()/implicit submission can leave event.submitter null; fall
  // back to the dialog's primary button so submission never dies silently.
  const button = event.submitter || $('newForm').querySelector('button.primary');
  if (button) button.disabled = true;
  try {
    const evidencePath = $('newEvidencePath').value.trim().replace(/\\/g, '/');
    if (evidencePath && !/^(wiki|drafts)\/[A-Za-z0-9_.@/-]+\.md$/.test(evidencePath)) throw new Error('关联知识必须是 wiki/... 或 drafts/... 的 Markdown 路径');
    const evidence_refs = evidencePath ? [{type: evidencePath.startsWith('wiki/') ? 'wiki' : 'candidate', path: evidencePath}] : [];
    const classification = MAIL_INTENTS[$('newIntent').value] || MAIL_INTENTS.message;
    $('newRecordKind').value = classification.record_kind;
    $('newDeliveryReason').value = classification.delivery_reason;
    const result = await api('send', {title:$('newTitle').value.trim(), body:$('newBody').value.trim(), to:$('recipient').value.trim(), record_kind:classification.record_kind, delivery_reason:classification.delivery_reason, evidence_refs});
    $('composeDialog').close(); $('newForm').reset(); selected = result.thread_id; filter = 'all'; switchWorkspace('mail'); document.body.classList.add('reading'); await refresh(); toast('协作记录已保存，可在详情查看真实回执');
  } catch (error) { $('newError').textContent = error.message; } finally { if (button) button.disabled = false; }
};
$('memberForm').onsubmit = async event => {
  event.preventDefault();
  const button = event.submitter || $('memberForm').querySelector('button.primary');
  if (button) button.disabled = true;
  const kind = $('memberKind').value === 'member' ? '成员' : '助手';
  const memberId = $('memberId').value.trim().replace(/^@/, '');
  const displayName = $('memberName').value.trim();
  const controller = $('memberController').value.trim();
  const body = `## 建立${kind}档案申请\n\n成员类型：${kind}\n稳定 ID：@${memberId}\n显示名称：${displayName}\n职责：${$('memberRole').value.trim()}\n工作范围：${$('memberScope').value.trim() || '未指定'}\n补充说明：${$('memberNotes').value.trim() || '无'}\n\n请由你根据团队约定建立或更新共享 profiles/agents/${memberId}.md；完成后回复结果。`;
  $('memberError').textContent = '';
  try {
    const result = await api('send', {to:controller, title:`建立${kind}档案：${displayName}`, body, record_kind:'handoff', delivery_reason:'handoff'});
    $('memberDialog').close(); $('memberForm').reset(); selected = result.thread_id; filter = 'all'; switchWorkspace('mail'); document.body.classList.add('reading'); await refresh(); toast('建档申请已发送，等待负责 Agent 处理');
  } catch (error) { $('memberError').textContent = error.message; } finally { if (button) button.disabled = false; }
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
  const timeline = threadTimeline(thread).map(event => `<li><time>${escapeHtml(formatTime(event.timestamp))}</time><span class="timeline-dot"></span><div><b>${escapeHtml(timelineLabel(event.type))}</b><span>${escapeHtml(name(event.actor))}${event.sessionId ? ` · Session ${escapeHtml(event.sessionId)}` : ''}${event.machineId ? ` · Machine ${escapeHtml(event.machineId)}` : ''}</span></div></li>`).join('') || '<li class="timeline-empty">暂无回执事件；目前只有消息正文。</li>';
  $('detailTitle').textContent = '协作事项详情';
  $('detailPanel').setAttribute('aria-label', '对话详情');
  $('detailContent').innerHTML = `<h4>参与者</h4><p>${escapeHtml((thread.participants || []).map(name).join(' · '))}</p><h4>跨机器来源</h4><p>${escapeHtml(syncState)}</p><p class="quiet-note">${escapeHtml(connection?.sync?.message || 'Mail Core 只记录消息来源，不会自动判断 Git 是否已同步。')}</p><h4>协作时间线</h4><p class="quiet-note">同一事项可以跨多个 Agent、Session 和机器继续。这里只展示已发生的发送、呈现、已读、确认和回复，不代表在线或可执行。</p><ol class="evidence-timeline">${timeline}</ol><details open><summary>展开每条事实的来源</summary><p>Thread：${escapeHtml(thread.thread_id)}</p>${(thread.messages || []).map(message => `<p>${escapeHtml(name(message.from))} · ${senderKind(message).label} · ${recordKindLabel(message.record_kind)} · Session ${escapeHtml(message.origin_session_id || '未记录')} · Machine ${escapeHtml(message.origin_machine_id || '未记录')}${message.read_at ? ' · 本机已读' : ''}</p>${deliverySummary(message)}`).join('')}</details>`;
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
document.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.thread) choose(button.dataset.thread);
  if (button.dataset.filter) { switchWorkspace('mail'); filter = button.dataset.filter; renderList(); }
  if (button.dataset.view) switchWorkspace(button.dataset.view);
  if (button.hasAttribute('data-create')) openCompose();
  if (button.hasAttribute('data-create-intent')) openCompose(button.getAttribute('data-create-intent') || 'handoff');
  if (button.hasAttribute('data-refresh-memory')) { memory = null; renderMemory(); }
  if (button.hasAttribute('data-memory-path')) openMemoryItem(button.getAttribute('data-memory-path'));
  if (button.hasAttribute('data-memory-collab-path')) openCompose('knowledge_ref', {evidencePath: button.getAttribute('data-memory-collab-path') || '', title: `请审核：${button.getAttribute('data-memory-collab-title') || '这条知识'}`, body: `请查看关联知识并留下审核意见。\n\n知识路径：${button.getAttribute('data-memory-collab-path') || ''}`});
  if (button.hasAttribute('data-memory-kind')) { memoryKindFilter = button.getAttribute('data-memory-kind') || 'all'; renderMemory(); }
  if (button.hasAttribute('data-member-add')) openMemberDialog(button.getAttribute('data-member-add'), button.getAttribute('data-member-agent') || '');
  if (button.hasAttribute('data-team-sync')) {
    if (!window.confirm('将整理共享文件、拉取并合并远端、提交本机变更，再推送到团队仓库。继续吗？')) return;
    button.disabled = true;
    try {
      team = await api('team/sync', {push:true, message:'同步 OKS 团队资料'});
      toast(team.actions?.length ? `团队资料已同步：${team.actions.join('、')}` : '没有新的团队文件需要同步');
      renderAgents(); appendAgentGuide();
    } catch (error) {
      toast(`团队同步失败：${error.message}`);
    } finally { button.disabled = false; }
  }
  if (button.dataset.threadAction === 'details') openDetailsPanel();
  if (button.dataset.threadAction === 'archive') updateArchive('archive');
  if (button.dataset.threadAction === 'unarchive') updateArchive('unarchive');
  if (button.hasAttribute('data-close')) { const dialog = button.closest('dialog'); if (dialog?.id === 'threadActionsDialog') closeThreadActions(); else dialog?.close(); }
});
$('back').onclick = () => document.body.classList.remove('reading');

switchWorkspace('mail'); renderList(); renderConversation();
refresh().catch(error => { loading = false; renderList(); $('runtimeText').textContent = `读取 Mail 失败：${error.message}`; toast(error.message); });
refreshConnection().catch(error => { $('runtimeText').textContent = `Mail 已连接，状态读取失败：${error.message}`; });
