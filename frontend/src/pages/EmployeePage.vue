<template>
  <div class="page-container">
    <NavBar />
    <div class="page-body">
      <!-- 左栏：对话列表 -->
      <div class="sidebar">
        <button class="btn-new-chat" @click="createNewTicket">+ 发起新对话</button>
        <div class="ticket-list">
          <div
            v-for="t in tickets"
            :key="t.id"
            :class="['ticket-item', { active: currentTicket?.id === t.id }]"
            @click="selectTicket(t)"
          >
            <div class="ticket-title">{{ t.title }}</div>
            <div class="ticket-meta">
              <span :class="['status-dot', `dot-${t.status}`]"></span>
              <span class="status-text">{{ statusLabel(t.status) }}</span>
              <span class="ticket-time">{{ formatTime(t.updated_at) }}</span>
            </div>
          </div>
          <div v-if="tickets.length === 0" class="empty-sidebar">暂无对话</div>
        </div>
      </div>

      <!-- 右栏：聊天区域 -->
      <div class="chat-area">
        <template v-if="currentTicket">
          <!-- 聊天头部 -->
          <div class="chat-header">
            <span class="chat-title">{{ currentTicket.title }}</span>
            <span :class="['header-status', `hs-${currentTicket.status}`]">
              {{ statusLabel(currentTicket.status) }}
            </span>
          </div>

          <!-- 消息列表 -->
          <div class="messages-container" ref="messagesRef">
            <div
              v-for="(msg, idx) in messages"
              :key="msg.id"
              :class="['message-row', `role-${msg.role}`, 'msg-enter']"
              :style="{ animationDelay: idx > messages.length - 3 ? '0.1s' : '0s' }"
            >
              <div class="avatar" v-if="msg.role !== 'user'">
                <span v-if="msg.role === 'ai'">🤖</span>
                <span v-else>👨‍💼</span>
              </div>
              <div class="bubble">
                <div class="bubble-role">{{ roleLabel(msg.role) }}</div>
                <div class="bubble-content" v-html="renderContent(msg.content)"></div>
                <div class="bubble-time">{{ formatMsgTime(msg.created_at) }}</div>
              </div>
              <div class="avatar" v-if="msg.role === 'user'">
                <span>😊</span>
              </div>
            </div>
            <div v-if="aiLoading" class="message-row role-ai msg-enter">
              <div class="avatar">🤖</div>
              <div class="bubble">
                <div class="bubble-role">AI 助手</div>
                <div class="bubble-content typing">
                  <span class="dot-loader">
                    <span></span><span></span><span></span>
                  </span>
                  正在思考中...
                </div>
              </div>
            </div>
          </div>

          <!-- 输入区域 -->
          <div v-if="canSend" class="input-area">
            <textarea
              v-model="inputText"
              placeholder="输入你的问题..."
              @keydown.enter.exact.prevent="sendMsg"
              rows="2"
            ></textarea>
            <button class="btn-send" :disabled="!inputText.trim() || aiLoading" @click="sendMsg">
              发送
            </button>
          </div>
          <div v-else class="input-area readonly-hint">
            <span v-if="currentTicket.status === 'pending'">已转接人工，等待坐席接入...</span>
            <span v-else>对话已结束</span>
          </div>

          <!-- 操作按钮 -->
          <div v-if="showActions" class="action-bar">
            <button class="btn-action btn-resolve" @click="doResolve">
              模型已解决
            </button>
            <button class="btn-action btn-transfer" @click="doTransfer">
              转接人工
            </button>
          </div>
        </template>

        <template v-else>
          <div class="no-ticket">
            <h3>选择左侧对话或发起新对话</h3>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import NavBar from '../components/NavBar.vue'
import {
  listTickets,
  createTicket,
  getMessages,
  sendMessage,
  sendUserMessageDirect,
  transferTicket,
  resolveTicket,
  type Ticket,
  type Message,
} from '../services/conversation'

const tickets = ref<Ticket[]>([])
const currentTicket = ref<Ticket | null>(null)
const messages = ref<Message[]>([])
const inputText = ref('')
const aiLoading = ref(false)
const messagesRef = ref<HTMLElement | null>(null)

// ── 计算属性 ────────────────────────────────────────────
const canSend = computed(() => {
  const s = currentTicket.value?.status
  return s === 'chatting' || s === 'handling'
})

const showActions = computed(() => {
  if (!currentTicket.value) return false
  if (currentTicket.value.status !== 'chatting') return false
  // 至少有一条 AI 消息才显示操作按钮
  return messages.value.some(m => m.role === 'ai')
})

// ── 加载数据 ────────────────────────────────────────────
async function loadTickets() {
  try {
    tickets.value = await listTickets()
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
async function createNewTicket() {
  try {
    const ticket = await createTicket()
    await loadTickets()
    selectTicket(ticket)
  } catch (e) {
    console.error('创建工单失败', e)
  }
}

function selectTicket(t: Ticket) {
  currentTicket.value = t
  loadMessages(t.id)
}

async function sendMsg() {
  if (!inputText.value.trim() || !currentTicket.value || aiLoading.value) return

  const content = inputText.value.trim()
  inputText.value = ''

  const isHandling = currentTicket.value.status === 'handling'

  if (isHandling) {
    // 人工处理中 → 员工直接发消息，不触发 AI
    try {
      const msg = await sendUserMessageDirect(currentTicket.value.id, content)
      messages.value.push(msg)
      await scrollToBottom()
    } catch (e: any) {
      console.error('发送消息失败', e)
      alert('发送失败: ' + (e.response?.data?.error || e.message))
    }
  } else {
    // AI 对话中 → 发消息并等待 AI 回复
    aiLoading.value = true
    try {
      const { user_msg, ai_msg } = await sendMessage(currentTicket.value.id, content)
      messages.value.push(user_msg, ai_msg)
      await loadTickets()
      const updated = tickets.value.find(t => t.id === currentTicket.value?.id)
      if (updated) currentTicket.value = updated
      await scrollToBottom()
    } catch (e: any) {
      console.error('发送消息失败', e)
      alert('发送失败: ' + (e.response?.data?.error || e.message))
    } finally {
      aiLoading.value = false
    }
  }
}

async function doTransfer() {
  if (!currentTicket.value) return
  if (!confirm('确定转接人工客服？')) return
  try {
    const updated = await transferTicket(currentTicket.value.id)
    currentTicket.value = updated
    await loadTickets()
    await loadMessages(updated.id)
  } catch (e: any) {
    alert('转接失败: ' + (e.response?.data?.error || e.message))
  }
}

async function doResolve() {
  if (!currentTicket.value) return
  try {
    const updated = await resolveTicket(currentTicket.value.id)
    currentTicket.value = updated
    await loadTickets()
  } catch (e: any) {
    alert('操作失败: ' + (e.response?.data?.error || e.message))
  }
}

// ── 工具函数 ────────────────────────────────────────────
function statusLabel(s: string): string {
  const m: Record<string, string> = {
    chatting: 'AI 对话中',
    pending: '等待人工',
    handling: '坐席处理中',
    resolved: 'AI 已解决',
    closed: '已完结',
    reviewed: '已质检',
  }
  return m[s] || s
}

function roleLabel(r: string): string {
  const m: Record<string, string> = { user: '我', ai: 'AI 助手', agent: '人工坐席' }
  return m[r] || r
}

function renderContent(text: string): string {
  // 简单换行处理
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

// ── 轮询（实时接收坐席消息和工单状态变化） ──────────────
let pollTimer: ReturnType<typeof setInterval> | null = null

function startPoll() {
  pollTimer = setInterval(async () => {
    if (currentTicket.value) {
      const s = currentTicket.value.status
      if (s === 'handling' || s === 'pending') {
        const oldLen = messages.value.length
        await loadMessages(currentTicket.value.id)
        if (messages.value.length > oldLen) {
          await scrollToBottom()
        }
      }
    }
    // 刷新工单列表（状态可能变化）
    await loadTickets()
    // 同步更新当前工单状态
    if (currentTicket.value) {
      const updated = tickets.value.find(t => t.id === currentTicket.value?.id)
      if (updated) currentTicket.value = updated
    }
  }, 3000)
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
  width: 280px;
  background: #fff;
  border-right: 1px solid #e8eaed;
  display: flex;
  flex-direction: column;
}

.btn-new-chat {
  margin: 12px;
  padding: 10px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-new-chat:hover {
  background: #337ecc;
}

.ticket-list {
  flex: 1;
  overflow-y: auto;
}

.ticket-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f2f3f5;
  transition: background 0.15s;
}

.ticket-item:hover {
  background: #f5f7fa;
}

.ticket-item.active {
  background: #ecf5ff;
  border-left: 3px solid #409eff;
}

.ticket-title {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.ticket-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot-chatting { background: #409eff; }
.dot-pending { background: #e6a23c; }
.dot-handling { background: #f56c6c; }
.dot-resolved { background: #67c23a; }
.dot-closed { background: #909399; }
.dot-reviewed { background: #67c23a; }

.ticket-time {
  margin-left: auto;
}

.empty-sidebar {
  text-align: center;
  color: #c0c4cc;
  padding: 32px 0;
  font-size: 13px;
}

/* ── 右栏 ── */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.chat-header {
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e8eaed;
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-title {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
}

.header-status {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
}

.hs-chatting { background: #ecf5ff; color: #409eff; }
.hs-pending { background: #fdf6ec; color: #e6a23c; }
.hs-handling { background: #fef0f0; color: #f56c6c; }
.hs-resolved { background: #f0f9eb; color: #67c23a; }
.hs-closed { background: #f4f4f5; color: #909399; }
.hs-reviewed { background: #f0f9eb; color: #67c23a; }

/* ── 消息 ── */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.message-row {
  display: flex;
  margin-bottom: 16px;
  align-items: flex-end;
  gap: 8px;
}

.msg-enter {
  animation: msgSlideIn 0.35s ease-out both;
}

@keyframes msgSlideIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.role-user {
  justify-content: flex-end;
}

.role-ai,
.role-agent {
  justify-content: flex-start;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  background: #f0f2f5;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}

.role-user .avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.role-ai .avatar {
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.role-agent .avatar {
  background: linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%);
}

.bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 16px;
  position: relative;
  transition: transform 0.15s;
}

.bubble:hover {
  transform: scale(1.01);
}

.role-user .bubble {
  background: linear-gradient(135deg, #409eff 0%, #6c5ce7 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 3px 12px rgba(64, 158, 255, 0.3);
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
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(103, 194, 58, 0.15);
}

.bubble-role {
  font-size: 11px;
  margin-bottom: 4px;
  opacity: 0.7;
  font-weight: 500;
}

.role-user .bubble-role { color: rgba(255,255,255,0.85); }

.bubble-content {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.bubble-time {
  font-size: 11px;
  margin-top: 4px;
  opacity: 0.45;
  text-align: right;
}

.typing {
  color: #909399;
  display: flex;
  align-items: center;
  gap: 6px;
}

.dot-loader {
  display: inline-flex;
  gap: 3px;
}

.dot-loader span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #409eff;
  animation: dotBounce 1.4s infinite ease-in-out both;
}

.dot-loader span:nth-child(1) { animation-delay: -0.32s; }
.dot-loader span:nth-child(2) { animation-delay: -0.16s; }
.dot-loader span:nth-child(3) { animation-delay: 0s; }

@keyframes dotBounce {
  0%, 80%, 100% { transform: scale(0.4); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ── 输入区 ── */
.input-area {
  padding: 12px 20px;
  background: #fff;
  border-top: 1px solid #e8eaed;
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.input-area textarea {
  flex: 1;
  resize: none;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border 0.2s;
}

.input-area textarea:focus {
  border-color: #409eff;
}

.btn-send {
  padding: 8px 20px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-send:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}

.readonly-hint {
  justify-content: center;
  color: #909399;
  font-size: 14px;
  padding: 16px;
}

/* ── 操作按钮 ── */
.action-bar {
  padding: 8px 20px;
  background: #fff;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.btn-action {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid;
  transition: all 0.2s;
}

.btn-resolve {
  background: #f0f9eb;
  color: #67c23a;
  border-color: #c2e7b0;
}

.btn-resolve:hover {
  background: #67c23a;
  color: #fff;
}

.btn-transfer {
  background: #fdf6ec;
  color: #e6a23c;
  border-color: #f5dab1;
}

.btn-transfer:hover {
  background: #e6a23c;
  color: #fff;
}

.no-ticket {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}
</style>
