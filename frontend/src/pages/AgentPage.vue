<template>
  <div class="page-container">
    <NavBar />
    <div class="page-body">
      <!-- 左栏：工单队列 -->
      <div class="sidebar">
        <div class="filter-row">
          <select v-model="filterStatus" @change="loadTickets" class="filter-select">
            <option value="pending,handling">全部待办</option>
            <option value="pending">待处理</option>
            <option value="handling">处理中</option>
          </select>
        </div>
        <div class="ticket-list">
          <div
            v-for="t in tickets"
            :key="t.id"
            :class="['ticket-card', { active: currentTicket?.id === t.id }]"
            @click="selectTicket(t)"
          >
            <div class="card-header">
              <span class="ticket-no">#{{ t.id }}</span>
              <span :class="['status-tag', `tag-${t.status}`]">{{ statusLabel(t.status) }}</span>
            </div>
            <div class="card-title">{{ t.title }}</div>
            <div class="card-meta">
              <span v-if="t.category" class="category-tag">{{ t.category }}</span>
              <span class="card-time">{{ formatTime(t.updated_at) }}</span>
            </div>
          </div>
          <div v-if="tickets.length === 0" class="empty-sidebar">暂无工单</div>
        </div>
      </div>

      <!-- 中栏：聊天区域 -->
      <div class="chat-area">
        <template v-if="currentTicket">
          <div class="chat-header">
            <span class="chat-title">#{{ currentTicket.id }} {{ currentTicket.title }}</span>
            <span :class="['header-status', `hs-${currentTicket.status}`]">
              {{ statusLabel(currentTicket.status) }}
            </span>
          </div>

          <div class="messages-container" ref="messagesRef">
            <div
              v-for="msg in messages"
              :key="msg.id"
              :class="['message-row', `role-${msg.role}`, 'msg-enter']"
            >
              <div class="avatar" v-if="msg.role !== 'agent'">
                <span v-if="msg.role === 'ai'">🤖</span>
                <span v-else>😊</span>
              </div>
              <div class="bubble">
                <div class="bubble-role">{{ roleLabel(msg.role) }}</div>
                <div class="bubble-content" v-html="renderContent(msg.content)"></div>
                <div class="bubble-time">{{ formatMsgTime(msg.created_at) }}</div>
              </div>
              <div class="avatar" v-if="msg.role === 'agent'">
                <span>👨‍💼</span>
              </div>
            </div>
          </div>

          <!-- 坐席输入框 -->
          <div v-if="currentTicket.status === 'handling'" class="input-area">
            <textarea
              v-model="inputText"
              placeholder="输入回复内容..."
              @keydown.enter.exact.prevent="sendMsg"
              rows="2"
            ></textarea>
            <button class="btn-send" :disabled="!inputText.trim() || sending" @click="sendMsg">
              发送
            </button>
          </div>
          <div v-else class="input-area readonly-hint">
            <span v-if="currentTicket.status === 'pending'">请先接单后回复</span>
            <span v-else>工单已结束</span>
          </div>

          <!-- 操作按钮栏 -->
          <div class="action-bar">
            <div class="action-left">
              <select v-model="selectedCategory" @change="onCategoryChange" class="category-select">
                <option value="">选择分类...</option>
                <option value="技术问题">技术问题</option>
                <option value="账号问题">账号问题</option>
                <option value="业务咨询">业务咨询</option>
                <option value="投诉建议">投诉建议</option>
                <option value="其他">其他</option>
              </select>
            </div>
            <div class="action-right">
              <button
                v-if="currentTicket.status === 'pending'"
                class="btn-action btn-accept"
                @click="doAccept"
              >
                接单
              </button>
              <button
                v-if="currentTicket.status === 'handling'"
                class="btn-action btn-close"
                @click="doClose"
              >
                结束工单
              </button>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="no-ticket">
            <h3>请在左侧选择一个工单</h3>
          </div>
        </template>
      </div>

      <!-- 右栏：智能助手面板 -->
      <div class="assist-panel" v-if="currentTicket">
        <div class="panel-header">
          <span>智能助手</span>
          <button
            class="btn-assist"
            :disabled="assistLoading"
            @click="doAssist"
          >
            {{ assistLoading ? '分析中...' : '智能分析' }}
          </button>
        </div>

        <template v-if="assistResult">
          <!-- 意图识别 -->
          <div class="assist-section">
            <div class="section-title">意图识别</div>
            <div class="intent-row">
              <span class="intent-label">{{ assistResult.intent }}</span>
              <span class="intent-confidence">{{ (assistResult.confidence * 100).toFixed(0) }}%</span>
            </div>
            <div class="keywords" v-if="assistResult.keywords.length">
              <span v-for="kw in assistResult.keywords" :key="kw" class="keyword-tag">{{ kw }}</span>
            </div>
          </div>

          <!-- 推荐回复 -->
          <div class="assist-section">
            <div class="section-title">推荐回复</div>
            <div class="suggestion-box">{{ assistResult.suggestion }}</div>
            <div class="suggest-actions">
              <button class="btn-sm btn-adopt" @click="adoptSuggestion">一键采用</button>
              <button class="btn-sm btn-edit" @click="editSuggestion">编辑后发送</button>
            </div>
          </div>

          <!-- 引用来源 -->
          <div class="assist-section" v-if="assistResult.sources.length">
            <div class="section-title">引用来源</div>
            <div v-for="(src, i) in assistResult.sources" :key="i" class="source-item">
              <span class="source-type">{{ src.source_type === 'qa' ? 'QA库' : '知识库' }}</span>
              <span class="source-score">{{ (src.score * 100).toFixed(0) }}%</span>
              <div class="source-content">{{ src.content.substring(0, 120) }}...</div>
            </div>
          </div>
        </template>

        <div v-else-if="!assistLoading" class="assist-empty">
          点击「智能分析」按钮获取推荐回复
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import NavBar from '../components/NavBar.vue'
import {
  listAgentTickets,
  getMessages,
  acceptTicket,
  closeTicket,
  sendAgentMessage,
  getAssist,
  updateCategory,
  type Ticket,
  type Message,
  type AssistResult,
} from '../services/agent'

const tickets = ref<Ticket[]>([])
const currentTicket = ref<Ticket | null>(null)
const messages = ref<Message[]>([])
const inputText = ref('')
const sending = ref(false)
const filterStatus = ref('pending,handling')
const selectedCategory = ref('')
const messagesRef = ref<HTMLElement | null>(null)

// 智能助手
const assistResult = ref<AssistResult | null>(null)
const assistLoading = ref(false)

// 自动刷新
let pollTimer: ReturnType<typeof setInterval> | null = null

// ── 加载数据 ────────────────────────────────────────────
async function loadTickets() {
  try {
    tickets.value = await listAgentTickets(filterStatus.value)
  } catch (e) {
    console.error('加载工单列表失败', e)
  }
}

async function loadMessages(ticketId: number) {
  try {
    messages.value = await getMessages(ticketId)
    await scrollToBottom()
  } catch (e) {
    console.error('加载消息失败', e)
  }
}

// ── 操作 ────────────────────────────────────────────────
function selectTicket(t: Ticket) {
  currentTicket.value = t
  selectedCategory.value = t.category || ''
  assistResult.value = null
  loadMessages(t.id)
}

async function sendMsg() {
  if (!inputText.value.trim() || !currentTicket.value || sending.value) return
  const content = inputText.value.trim()
  inputText.value = ''
  sending.value = true

  try {
    const msg = await sendAgentMessage(currentTicket.value.id, content)
    messages.value.push(msg)
    await scrollToBottom()
  } catch (e: any) {
    alert('发送失败: ' + (e.response?.data?.error || e.message))
  } finally {
    sending.value = false
  }
}

async function doAccept() {
  if (!currentTicket.value) return
  try {
    const updated = await acceptTicket(currentTicket.value.id)
    currentTicket.value = updated
    await loadTickets()
  } catch (e: any) {
    alert('接单失败: ' + (e.response?.data?.error || e.message))
  }
}

async function doClose() {
  if (!currentTicket.value) return
  if (!confirm('确定结束此工单？')) return
  try {
    const updated = await closeTicket(currentTicket.value.id)
    currentTicket.value = updated
    await loadTickets()
    await loadMessages(updated.id)
  } catch (e: any) {
    alert('结束失败: ' + (e.response?.data?.error || e.message))
  }
}

async function doAssist() {
  if (!currentTicket.value) return
  assistLoading.value = true
  assistResult.value = null
  try {
    assistResult.value = await getAssist(currentTicket.value.id)
  } catch (e: any) {
    alert('智能分析失败: ' + (e.response?.data?.error || e.message))
  } finally {
    assistLoading.value = false
  }
}

function adoptSuggestion() {
  if (assistResult.value) {
    inputText.value = assistResult.value.suggestion
  }
}

function editSuggestion() {
  if (assistResult.value) {
    inputText.value = assistResult.value.suggestion
    // 聚焦输入框
    nextTick(() => {
      const textarea = document.querySelector('.input-area textarea') as HTMLTextAreaElement
      if (textarea) textarea.focus()
    })
  }
}

async function onCategoryChange() {
  if (!currentTicket.value || !selectedCategory.value) return
  try {
    const updated = await updateCategory(currentTicket.value.id, selectedCategory.value)
    currentTicket.value = updated
    await loadTickets()
  } catch (e: any) {
    alert('分类更新失败: ' + (e.response?.data?.error || e.message))
  }
}

// ── 工具函数 ────────────────────────────────────────────
function statusLabel(s: string): string {
  const m: Record<string, string> = {
    chatting: 'AI 对话中', pending: '待处理', handling: '处理中',
    resolved: 'AI 已解决', closed: '已完结', reviewed: '已质检',
  }
  return m[s] || s
}

function roleLabel(r: string): string {
  const m: Record<string, string> = { user: '员工', ai: 'AI 助手', agent: '坐席' }
  return m[r] || r
}

function renderContent(text: string): string {
  return text.replace(/\n/g, '<br>')
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatMsgTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function scrollToBottom() {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

// ── 定时刷新消息（坐席端需要看到员工新消息） ────────────
function startPoll() {
  pollTimer = setInterval(async () => {
    if (currentTicket.value && currentTicket.value.status === 'handling') {
      const oldLen = messages.value.length
      await loadMessages(currentTicket.value.id)
      if (messages.value.length > oldLen) {
        await scrollToBottom()
      }
    }
    // 也刷新工单列表
    await loadTickets()
  }, 5000)
}

// ── 初始化 ──────────────────────────────────────────────
onMounted(() => {
  loadTickets()
  startPoll()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.page-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ── 左栏 ── */
.sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e8eaed;
  display: flex;
  flex-direction: column;
}

.filter-row {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f1f3;
}

.filter-select {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
}

.ticket-list {
  flex: 1;
  overflow-y: auto;
}

.ticket-card {
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid #f2f3f5;
  transition: background 0.15s;
}

.ticket-card:hover {
  background: #f5f7fa;
}

.ticket-card.active {
  background: #ecf5ff;
  border-left: 3px solid #409eff;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.ticket-no {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.status-tag {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 10px;
}

.tag-pending { background: #fef0f0; color: #f56c6c; }
.tag-handling { background: #fdf6ec; color: #e6a23c; }
.tag-closed { background: #f4f4f5; color: #909399; }
.tag-resolved { background: #f0f9eb; color: #67c23a; }
.tag-reviewed { background: #f0f9eb; color: #67c23a; }

.card-title {
  font-size: 13px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #909399;
}

.category-tag {
  background: #f0f2f5;
  padding: 0 6px;
  border-radius: 3px;
}

.card-time {
  margin-left: auto;
}

.empty-sidebar {
  text-align: center;
  color: #c0c4cc;
  padding: 32px 0;
  font-size: 13px;
}

/* ── 中栏 ── */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  min-width: 0;
}

.chat-header {
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #e8eaed;
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.header-status {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
}

.hs-pending { background: #fef0f0; color: #f56c6c; }
.hs-handling { background: #fdf6ec; color: #e6a23c; }
.hs-closed { background: #f4f4f5; color: #909399; }
.hs-resolved { background: #f0f9eb; color: #67c23a; }
.hs-reviewed { background: #f0f9eb; color: #67c23a; }

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.message-row {
  display: flex;
  margin-bottom: 12px;
  align-items: flex-end;
  gap: 8px;
}

.msg-enter {
  animation: msgSlideIn 0.3s ease-out both;
}

@keyframes msgSlideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.role-user { justify-content: flex-start; }
.role-ai { justify-content: flex-start; }
.role-agent { justify-content: flex-end; }

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}

.role-user .avatar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.role-ai .avatar { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
.role-agent .avatar { background: linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%); }

.bubble {
  max-width: 70%;
  padding: 8px 12px;
  border-radius: 14px;
  transition: transform 0.15s;
}

.bubble:hover { transform: scale(1.01); }

.role-user .bubble {
  background: linear-gradient(135deg, #409eff 0%, #6c5ce7 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 3px 10px rgba(64,158,255,0.25);
}

.role-ai .bubble {
  background: #fff;
  color: #303133;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  border: 1px solid #f0f1f3;
}

.role-agent .bubble {
  background: linear-gradient(135deg, #e8f8e5 0%, #d4fc79 100%);
  color: #303133;
  border-bottom-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(103,194,58,0.15);
}

.bubble-role {
  font-size: 11px;
  margin-bottom: 3px;
  opacity: 0.7;
  font-weight: 500;
}

.role-user .bubble-role { color: rgba(255,255,255,0.85); }

.bubble-content {
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.bubble-time {
  font-size: 10px;
  margin-top: 3px;
  opacity: 0.45;
  text-align: right;
}

.input-area {
  padding: 10px 16px;
  background: #fff;
  border-top: 1px solid #e8eaed;
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-area textarea {
  flex: 1;
  resize: none;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
}

.input-area textarea:focus {
  border-color: #409eff;
}

.btn-send {
  padding: 6px 16px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

.btn-send:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}

.readonly-hint {
  justify-content: center;
  color: #909399;
  font-size: 13px;
  padding: 14px;
}

.action-bar {
  padding: 6px 16px;
  background: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #f0f1f3;
}

.action-left, .action-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

.category-select {
  padding: 4px 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 12px;
  outline: none;
}

.btn-action {
  padding: 5px 14px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid;
  transition: all 0.2s;
}

.btn-accept {
  background: #ecf5ff;
  color: #409eff;
  border-color: #b3d8ff;
}

.btn-accept:hover {
  background: #409eff;
  color: #fff;
}

.btn-close {
  background: #fef0f0;
  color: #f56c6c;
  border-color: #fbc4c4;
}

.btn-close:hover {
  background: #f56c6c;
  color: #fff;
}

.no-ticket {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}

/* ── 右栏：智能助手 ── */
.assist-panel {
  width: 300px;
  background: #fff;
  border-left: 1px solid #e8eaed;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.panel-header {
  padding: 10px 14px;
  border-bottom: 1px solid #e8eaed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.btn-assist {
  padding: 4px 12px;
  font-size: 12px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-assist:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}

.assist-section {
  padding: 12px 14px;
  border-bottom: 1px solid #f0f1f3;
}

.section-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  font-weight: 500;
}

.intent-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.intent-label {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.intent-confidence {
  font-size: 13px;
  padding: 1px 8px;
  background: #f0f9eb;
  color: #67c23a;
  border-radius: 10px;
}

.keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.keyword-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 10px;
}

.suggestion-box {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
  background: #f5f7fa;
  padding: 10px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.suggest-actions {
  display: flex;
  gap: 6px;
}

.btn-sm {
  padding: 3px 10px;
  font-size: 11px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid;
  transition: all 0.2s;
}

.btn-adopt {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}

.btn-adopt:hover {
  background: #337ecc;
}

.btn-edit {
  background: #fff;
  color: #409eff;
  border-color: #b3d8ff;
}

.btn-edit:hover {
  background: #ecf5ff;
}

.source-item {
  margin-bottom: 8px;
  padding: 6px 8px;
  background: #fafafa;
  border-radius: 4px;
  border: 1px solid #f0f1f3;
}

.source-type {
  font-size: 11px;
  padding: 1px 6px;
  background: #e8f8e5;
  color: #67c23a;
  border-radius: 3px;
  margin-right: 4px;
}

.source-score {
  font-size: 11px;
  color: #909399;
}

.source-content {
  font-size: 12px;
  color: #606266;
  margin-top: 4px;
  line-height: 1.4;
}

.assist-empty {
  padding: 32px 14px;
  text-align: center;
  color: #c0c4cc;
  font-size: 13px;
}
</style>
