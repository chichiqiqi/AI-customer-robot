import api from './api'
import type { Ticket, Message } from './conversation'

export type { Ticket, Message }

export interface AssistResult {
  intent: string
  confidence: number
  keywords: string[]
  suggestion: string
  sources: Array<{
    content: string
    score: number
    source_type: string
    source_id: number
  }>
}

/** 获取坐席端工单列表（按状态筛选） */
export async function listAgentTickets(status?: string): Promise<Ticket[]> {
  const params: any = {}
  if (status) params.status = status
  const res = await api.get('/api/tickets', { params })
  return res.data.data || []
}

/** 获取工单消息列表 */
export async function getMessages(ticketId: number): Promise<Message[]> {
  const res = await api.get(`/api/tickets/${ticketId}/messages`)
  return res.data.data || []
}

/** 坐席接单 */
export async function acceptTicket(ticketId: number): Promise<Ticket> {
  const res = await api.post(`/api/tickets/${ticketId}/accept`)
  return res.data.data
}

/** 坐席结束工单 */
export async function closeTicket(ticketId: number): Promise<Ticket> {
  const res = await api.post(`/api/tickets/${ticketId}/close`)
  return res.data.data
}

/** 坐席发送消息 */
export async function sendAgentMessage(ticketId: number, content: string): Promise<Message> {
  const res = await api.post('/api/messages', {
    ticket_id: ticketId,
    content,
    sender_type: 'agent',
  })
  return res.data.data
}

/** 智能助手 — 获取推荐回复 */
export async function getAssist(ticketId: number): Promise<AssistResult> {
  const res = await api.post(`/api/tickets/${ticketId}/assist`)
  return res.data.data
}

/** 更新工单分类 */
export async function updateCategory(ticketId: number, category: string): Promise<Ticket> {
  const res = await api.patch(`/api/tickets/${ticketId}/category`, { category })
  return res.data.data
}
