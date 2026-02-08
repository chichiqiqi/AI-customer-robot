import api from './api'

export interface KnowledgeDoc {
  id: number
  filename: string
  status: string // processing | ready | failed
  chunk_count: number
  qa_count: number
  created_at: string
}

/** 上传 Markdown 文件 */
export async function uploadDocument(file: File): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await api.post('/api/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 上传+处理可能较久，120s 超时
  })
  return res.data
}

/** 获取文档列表 */
export async function listDocuments(): Promise<KnowledgeDoc[]> {
  const res = await api.get('/api/knowledge/docs')
  return res.data.data || []
}

/** 删除文档 */
export async function deleteDocument(docId: number): Promise<any> {
  const res = await api.delete(`/api/knowledge/docs/${docId}`)
  return res.data
}
