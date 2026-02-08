import api from './api'

export interface Ticket {
  id: number
  title: string
  status: string
  user_id: number
  agent_id: number | null
  category: string | null
  summary: string | null
  created_at: string
  updated_at: string
  closed_at: string | null
}

export interface Message {
  id: number
  ticket_id: number
  role: string // user | ai | agent
  content: string
  created_at: string
}

/** 获取当前用户的工单列表 */
export async function listTickets(status?: string): Promise<Ticket[]> {
  const params: any = {}
  if (status) params.status = status
  const res = await api.get('/api/tickets', { params })
  return res.data.data || []
}

/** 创建新工单 */
export async function createTicket(title: string = '新对话'): Promise<Ticket> {
  const res = await api.post('/api/tickets', { title })
  return res.data.data
}

/** 获取工单消息列表 */
export async function getMessages(ticketId: number): Promise<Message[]> {
  const res = await api.get(`/api/tickets/${ticketId}/messages`)
  return res.data.data || []
}

/** 发送消息（自动触发 AI 回复） */
export async function sendMessage(ticketId: number, content: string): Promise<{ user_msg: Message; ai_msg: Message }> {
  const res = await api.post('/api/messages', { ticket_id: ticketId, content })
  return res.data.data
}

/** 员工在人工处理中发送消息（不触发 AI） */
export async function sendUserMessageDirect(ticketId: number, content: string): Promise<Message> {
  const res = await api.post('/api/messages', { ticket_id: ticketId, content, sender_type: 'employee' })
  return res.data.data
}

/** 转接人工 */
export async function transferTicket(ticketId: number): Promise<Ticket> {
  const res = await api.post(`/api/tickets/${ticketId}/transfer`)
  return res.data.data
}

/** 标记 AI 已解决 */
export async function resolveTicket(ticketId: number): Promise<Ticket> {
  const res = await api.post(`/api/tickets/${ticketId}/resolve`)
  return res.data.data
}
