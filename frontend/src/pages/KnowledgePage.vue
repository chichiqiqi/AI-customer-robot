<template>
  <div class="page-container">
    <NavBar />
    <div class="page-body">
      <div class="knowledge-content">
        <!-- 上传区域 -->
        <div class="upload-section">
          <div
            class="upload-zone"
            :class="{ dragover: isDragOver }"
            @dragover.prevent="isDragOver = true"
            @dragleave.prevent="isDragOver = false"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".md"
              style="display: none"
              @change="handleFileSelect"
            />
            <div v-if="uploading" class="upload-status">
              <div class="spinner"></div>
              <p>正在处理：{{ uploadingFile }}...</p>
              <p class="upload-hint">切片 + 向量化 + QA 生成中，请稍候</p>
            </div>
            <div v-else class="upload-prompt">
              <div class="upload-icon">📄</div>
              <p class="upload-title">拖拽 Markdown 文件到此处上传</p>
              <p class="upload-hint">或点击此区域选择文件（仅支持 .md 格式）</p>
            </div>
          </div>
          <p v-if="uploadError" class="error-msg">{{ uploadError }}</p>
          <p v-if="uploadSuccess" class="success-msg">{{ uploadSuccess }}</p>
        </div>

        <!-- 文档列表 -->
        <div class="doc-list-section">
          <div class="section-header">
            <h3>知识库文档</h3>
            <button class="btn-refresh" @click="loadDocs">刷新</button>
          </div>

          <div v-if="loading" class="loading-text">加载中...</div>
          <div v-else-if="docs.length === 0" class="empty-text">暂无文档，请上传 Markdown 文件</div>

          <div v-else class="doc-table">
            <table>
              <thead>
                <tr>
                  <th>文件名</th>
                  <th>状态</th>
                  <th>切片数</th>
                  <th>QA 数</th>
                  <th>上传时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="doc in docs" :key="doc.id">
                  <td class="filename-cell">{{ doc.filename }}</td>
                  <td>
                    <span :class="['status-badge', `status-${doc.status}`]">
                      {{ statusLabel(doc.status) }}
                    </span>
                  </td>
                  <td>{{ doc.chunk_count }}</td>
                  <td>{{ doc.qa_count }}</td>
                  <td>{{ formatTime(doc.created_at) }}</td>
                  <td>
                    <button
                      class="btn-delete"
                      :disabled="deleting === doc.id"
                      @click="handleDelete(doc.id, doc.filename)"
                    >
                      {{ deleting === doc.id ? '删除中...' : '删除' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import NavBar from '../components/NavBar.vue'
import {
  uploadDocument,
  listDocuments,
  deleteDocument,
  type KnowledgeDoc,
} from '../services/knowledge'

const docs = ref<KnowledgeDoc[]>([])
const loading = ref(false)
const uploading = ref(false)
const uploadingFile = ref('')
const uploadError = ref('')
const uploadSuccess = ref('')
const deleting = ref<number | null>(null)
const isDragOver = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

// ── 加载文档列表 ────────────────────────────────────────
async function loadDocs() {
  loading.value = true
  try {
    docs.value = await listDocuments()
  } catch (e: any) {
    console.error('加载文档列表失败', e)
  } finally {
    loading.value = false
  }
}

// ── 上传 ────────────────────────────────────────────────
function triggerFileInput() {
  if (!uploading.value) {
    fileInput.value?.click()
  }
}

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    doUpload(input.files[0])
    input.value = '' // 重置，允许重复选择同一文件
  }
}

function handleDrop(event: DragEvent) {
  isDragOver.value = false
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    doUpload(files[0])
  }
}

async function doUpload(file: File) {
  uploadError.value = ''
  uploadSuccess.value = ''

  if (!file.name.endsWith('.md')) {
    uploadError.value = '仅支持 .md 格式文件'
    return
  }

  uploading.value = true
  uploadingFile.value = file.name

  try {
    const res = await uploadDocument(file)
    if (res.success) {
      uploadSuccess.value = `${file.name} 上传成功！切片 ${res.data.chunk_count} 个，QA ${res.data.qa_count} 个`
      await loadDocs()
    } else {
      uploadError.value = res.error || '上传失败'
    }
  } catch (e: any) {
    uploadError.value = e.response?.data?.error || e.message || '上传失败'
  } finally {
    uploading.value = false
    uploadingFile.value = ''
  }
}

// ── 删除 ────────────────────────────────────────────────
async function handleDelete(docId: number, filename: string) {
  if (!confirm(`确定删除「${filename}」及其所有切片和 QA 数据？`)) return

  deleting.value = docId
  try {
    await deleteDocument(docId)
    await loadDocs()
  } catch (e: any) {
    alert('删除失败: ' + (e.response?.data?.error || e.message))
  } finally {
    deleting.value = null
  }
}

// ── 工具函数 ────────────────────────────────────────────
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    processing: '处理中',
    ready: '已就绪',
    failed: '处理失败',
  }
  return map[status] || status
}

function formatTime(isoStr: string): string {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// ── 初始化 ──────────────────────────────────────────────
onMounted(() => {
  loadDocs()
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
  background: #f5f7fa;
  overflow-y: auto;
  padding: 24px;
}

.knowledge-content {
  max-width: 960px;
  margin: 0 auto;
}

/* ── 上传区域 ── */
.upload-section {
  margin-bottom: 32px;
}

.upload-zone {
  border: 2px dashed #d0d5dd;
  border-radius: 12px;
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.upload-zone:hover,
.upload-zone.dragover {
  border-color: #409eff;
  background: #f0f7ff;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.upload-title {
  font-size: 16px;
  color: #303133;
  font-weight: 500;
  margin-bottom: 4px;
}

.upload-hint {
  font-size: 13px;
  color: #909399;
}

.upload-status p {
  margin: 8px 0;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e4e7ed;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-msg {
  color: #f56c6c;
  font-size: 13px;
  margin-top: 8px;
}

.success-msg {
  color: #67c23a;
  font-size: 13px;
  margin-top: 8px;
}

/* ── 文档列表 ── */
.doc-list-section {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.btn-refresh {
  padding: 6px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fff;
  color: #606266;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.btn-refresh:hover {
  border-color: #409eff;
  color: #409eff;
}

.loading-text,
.empty-text {
  text-align: center;
  color: #909399;
  padding: 32px 0;
  font-size: 14px;
}

.doc-table table {
  width: 100%;
  border-collapse: collapse;
}

.doc-table th {
  text-align: left;
  padding: 10px 12px;
  font-size: 13px;
  color: #909399;
  border-bottom: 1px solid #ebeef5;
  font-weight: 500;
}

.doc-table td {
  padding: 12px;
  font-size: 14px;
  color: #303133;
  border-bottom: 1px solid #f2f3f5;
}

.filename-cell {
  font-weight: 500;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}

.status-processing {
  background: #fdf6ec;
  color: #e6a23c;
}

.status-ready {
  background: #f0f9eb;
  color: #67c23a;
}

.status-failed {
  background: #fef0f0;
  color: #f56c6c;
}

.btn-delete {
  padding: 4px 12px;
  border: 1px solid #f56c6c;
  border-radius: 4px;
  background: #fff;
  color: #f56c6c;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.btn-delete:hover:not(:disabled) {
  background: #f56c6c;
  color: #fff;
}

.btn-delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
