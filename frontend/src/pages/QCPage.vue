<template>
  <div class="page-container">
    <NavBar />
    <div class="page-body">
      <!-- 左栏：工单列表 -->
      <div class="sidebar">
        <div class="sidebar-title">已完结工单</div>
        <div class="ticket-list">
          <div
            v-for="t in tickets"
            :key="t.id"
            :class="['ticket-card', { active: currentTicket?.id === t.id }]"
            @click="selectTicket(t)"
          >
            <div class="card-header">
              <span class="ticket-no">#{{ t.id }}</span>
              <span v-if="t.has_qc" class="qc-badge">✅ 已质检</span>
              <span v-else class="qc-badge qc-pending">待质检</span>
            </div>
            <div class="card-title">{{ t.title }}</div>
            <div class="card-meta">
              <span v-if="t.category" class="category-tag">{{ t.category }}</span>
              <span class="card-time">{{ formatTime(t.closed_at || t.updated_at) }}</span>
            </div>
          </div>
          <div v-if="tickets.length === 0" class="empty-sidebar">暂无已完结工单</div>
        </div>
      </div>

      <!-- 右栏 -->
      <div class="main-area" v-if="currentTicket">
        <!-- 对话记录回看 -->
        <div class="chat-review">
          <div class="review-header">
            <span class="review-title">#{{ currentTicket.id }} {{ currentTicket.title }}</span>
            <span v-if="currentTicket.category" class="review-category">{{ currentTicket.category }}</span>
          </div>
          <div class="messages-container" ref="messagesRef">
            <div
              v-for="msg in messages"
              :key="msg.id"
              :class="['message-row', `role-${msg.role}`]"
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
          </div>
        </div>

        <!-- 质检评分 -->
        <div class="qc-form-area">
          <div class="form-title">
            {{ qcResult ? '质检评分（只读）' : '质检评分' }}
          </div>

          <!-- 三个维度 -->
          <div class="score-row">
            <label>知识准确性</label>
            <div class="stars">
              <span
                v-for="s in 5"
                :key="'a' + s"
                :class="['star', { filled: s <= formData.accuracy_score, readonly: !!qcResult }]"
                @click="!qcResult && (formData.accuracy_score = s)"
              >★</span>
            </div>
            <span class="score-num">{{ formData.accuracy_score }}/5</span>
          </div>

          <div class="score-row">
            <label>服务规范性</label>
            <div class="stars">
              <span
                v-for="s in 5"
                :key="'c' + s"
                :class="['star', { filled: s <= formData.compliance_score, readonly: !!qcResult }]"
                @click="!qcResult && (formData.compliance_score = s)"
              >★</span>
            </div>
            <span class="score-num">{{ formData.compliance_score }}/5</span>
          </div>

          <div class="score-row">
            <label>问题解决度</label>
            <div class="stars">
              <span
                v-for="s in 5"
                :key="'r' + s"
                :class="['star', { filled: s <= formData.resolution_score, readonly: !!qcResult }]"
                @click="!qcResult && (formData.resolution_score = s)"
              >★</span>
            </div>
            <span class="score-num">{{ formData.resolution_score }}/5</span>
          </div>

          <!-- 综合评语 -->
          <div class="comment-row">
            <label>综合评语</label>
            <textarea
              v-model="formData.comment"
              :readonly="!!qcResult"
              placeholder="请输入评语（选填）..."
              rows="3"
            ></textarea>
          </div>

          <!-- 综合分 -->
          <div class="total-row" v-if="qcResult">
            <span>综合得分：</span>
            <span class="total-score">{{ qcResult.total_score.toFixed(2) }}</span>
          </div>

          <!-- 提交按钮 -->
          <button
            v-if="!qcResult"
            class="btn-submit"
            :disabled="!canSubmit || submitting"
            @click="doSubmit"
          >
            {{ submitting ? '提交中...' : '提交评分' }}
          </button>
        </div>
      </div>

      <div class="main-area no-ticket" v-else>
        <h3>请在左侧选择一个工单进行质检</h3>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import NavBar from '../components/NavBar.vue'
import {
  listQCTickets,
  submitQCResult,
  getQCResult,
  getMessages,
  type QCTicket,
  type QCResult,
  type Message,
} from '../services/qc'

const tickets = ref<QCTicket[]>([])
const currentTicket = ref<QCTicket | null>(null)
const messages = ref<Message[]>([])
const qcResult = ref<QCResult | null>(null)
const submitting = ref(false)
const messagesRef = ref<HTMLElement | null>(null)

const formData = reactive({
  accuracy_score: 0,
  compliance_score: 0,
  resolution_score: 0,
  comment: '',
})

const canSubmit = computed(() => {
  return formData.accuracy_score > 0
    && formData.compliance_score > 0
    && formData.resolution_score > 0
})

// ── 加载数据 ────────────────────────────────────────────
async function loadTickets() {
  try {
    tickets.value = await listQCTickets()
  } catch (e) {
    console.error('加载工单列表失败', e)
  }
}

async function selectTicket(t: QCTicket) {
  currentTicket.value = t
  qcResult.value = null
  formData.accuracy_score = 0
  formData.compliance_score = 0
  formData.resolution_score = 0
  formData.comment = ''

  // 加载消息
  try {
    messages.value = await getMessages(t.id)
  } catch (e) {
    console.error('加载消息失败', e)
  }

  // 如果已质检，加载质检结果
  if (t.has_qc) {
    try {
      const result = await getQCResult(t.id)
      if (result) {
        qcResult.value = result
        formData.accuracy_score = result.accuracy_score
        formData.compliance_score = result.compliance_score
        formData.resolution_score = result.resolution_score
        formData.comment = result.comment || ''
      }
    } catch (e) {
      console.error('加载质检结果失败', e)
    }
  }
}

async function doSubmit() {
  if (!currentTicket.value || !canSubmit.value || submitting.value) return
  submitting.value = true

  try {
    const result = await submitQCResult({
      ticket_id: currentTicket.value.id,
      accuracy_score: formData.accuracy_score,
      compliance_score: formData.compliance_score,
      resolution_score: formData.resolution_score,
      comment: formData.comment || undefined,
    })
    qcResult.value = result
    // 更新左侧列表
    currentTicket.value.has_qc = true
    currentTicket.value.status = 'reviewed'
    await loadTickets()
    // 同步当前工单
    const updated = tickets.value.find(t => t.id === currentTicket.value?.id)
    if (updated) currentTicket.value = updated
  } catch (e: any) {
    alert('提交失败: ' + (e.response?.data?.error || e.message))
  } finally {
    submitting.value = false
  }
}

// ── 工具函数 ────────────────────────────────────────────
function roleLabel(r: string): string {
  const m: Record<string, string> = { user: '员工', ai: 'AI 助手', agent: '人工坐席' }
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

// ── 初始化 ──────────────────────────────────────────────
onMounted(() => {
  loadTickets()
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

.sidebar-title {
  padding: 14px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  border-bottom: 1px solid #e8eaed;
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

.qc-badge {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 10px;
  background: #f0f9eb;
  color: #67c23a;
}

.qc-pending {
  background: #fdf6ec;
  color: #e6a23c;
}

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

/* ── 右栏 ── */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-area.no-ticket {
  align-items: center;
  justify-content: center;
  color: #909399;
  background: #f5f7fa;
}

/* ── 对话回看 ── */
.chat-review {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.review-header {
  padding: 10px 20px;
  background: #fff;
  border-bottom: 1px solid #e8eaed;
  display: flex;
  align-items: center;
  gap: 10px;
}

.review-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.review-category {
  font-size: 12px;
  padding: 1px 8px;
  background: #f0f2f5;
  border-radius: 4px;
  color: #606266;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px 20px;
  background: #f5f7fa;
}

.message-row {
  display: flex;
  margin-bottom: 12px;
  align-items: flex-end;
  gap: 8px;
}

.role-user { justify-content: flex-end; }
.role-ai, .role-agent { justify-content: flex-start; }

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
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
}

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
  border-bottom-left-radius: 4px;
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

/* ── 质检表单 ── */
.qc-form-area {
  background: #fff;
  border-top: 1px solid #e8eaed;
  padding: 16px 24px;
  min-height: 220px;
}

.form-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 14px;
}

.score-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.score-row label {
  width: 90px;
  font-size: 13px;
  color: #606266;
  flex-shrink: 0;
}

.stars {
  display: flex;
  gap: 4px;
}

.star {
  font-size: 22px;
  color: #dcdfe6;
  cursor: pointer;
  transition: color 0.15s;
  user-select: none;
}

.star.filled {
  color: #f7ba2a;
}

.star.readonly {
  cursor: default;
}

.star:not(.readonly):hover {
  color: #f7ba2a;
}

.score-num {
  font-size: 13px;
  color: #909399;
  min-width: 30px;
}

.comment-row {
  margin-top: 12px;
  margin-bottom: 12px;
}

.comment-row label {
  display: block;
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}

.comment-row textarea {
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
  resize: none;
  box-sizing: border-box;
}

.comment-row textarea:focus {
  border-color: #409eff;
}

.comment-row textarea[readonly] {
  background: #f5f7fa;
  cursor: default;
}

.total-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #303133;
}

.total-score {
  font-size: 20px;
  font-weight: 700;
  color: #f7ba2a;
}

.btn-submit {
  padding: 8px 24px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-submit:hover {
  background: #337ecc;
}

.btn-submit:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}
</style>
