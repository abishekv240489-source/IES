import axios from 'axios'
import type { AuditEvent, DashboardData, InvoiceJob, JobStatus, PageResponse } from './types'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api/v1', timeout: 30_000 })

export const getDashboard = async () => (await api.get<DashboardData>('/dashboard')).data
export const getInvoices = async (status?: JobStatus) => (await api.get<PageResponse<InvoiceJob>>('/invoices', { params: { status, size: 100 } })).data
export const getInvoice = async (id: string) => (await api.get<InvoiceJob>(`/invoices/${id}`)).data
export const getEvents = async (id: string) => (await api.get<AuditEvent[]>(`/invoices/${id}/events`)).data
export const getInvoiceSourceUrl = (id: string) => `${api.defaults.baseURL}/invoices/${encodeURIComponent(id)}/source`

export async function uploadInvoices(files: File[]) {
  const form = new FormData()
  files.forEach(file => form.append('files', file))
  return (await api.post('/invoices', form)).data as { batchId: string; jobs: Array<{ id: string; filename: string; status: JobStatus; duplicate: boolean; message: string }> }
}

export async function reviewInvoice(id: string, extraction: Record<string, unknown>, approved: boolean, remarks: string) {
  return (await api.patch<InvoiceJob>(`/invoices/${id}/review`, { extraction, approved, remarks })).data
}
