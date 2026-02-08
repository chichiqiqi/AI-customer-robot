import api from './api'
import type { Ticket, Message } from './conversation'

export type { Ticket, Message }

export interface QCTicket extends Ticket {
  has_qc: boolean
}

export interface QCResult {
  id: number
  ticket_id: number
  accuracy_score: number
  compliance_score: number
  resolution_score: number
  total_score: number
  comment: string | null
  created_at: string
}

export interface QCScorePayload {
  ticket_id: number
  accuracy_score: number
  compliance_score: number
  resolution_score: number
  comment?: string
}

/** 获取可质检工单列表 */
export async function listQCTickets(): Promise<QCTicket[]> {
  const res = await api.get('/api/qc/tickets')
  return res.data.data || []
}

/** 提交质检评分 */
export async function submitQCResult(payload: QCScorePayload): Promise<QCResult> {
  const res = await api.post('/api/qc/results', payload)
  return res.data.data
}

/** 获取某工单的质检结果 */
export async function getQCResult(ticketId: number): Promise<QCResult | null> {
  const res = await api.get(`/api/qc/results/${ticketId}`)
  return res.data.data
}

/** 获取工单消息列表（复用） */
export async function getMessages(ticketId: number): Promise<Message[]> {
  const res = await api.get(`/api/tickets/${ticketId}/messages`)
  return res.data.data || []
}
