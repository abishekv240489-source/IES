export type JobStatus = 'QUEUED' | 'PREPROCESSING' | 'OCR_RUNNING' | 'MAPPING' | 'VALIDATING' | 'PENDING_REVIEW' | 'COMPLETED' | 'FAILED' | 'REJECTED'

export interface ExtractedField {
  value: string | number | null
  confidence: number
  source?: string
  page?: number | null
}

export interface InvoiceJob {
  id: string
  batchId: string
  filename: string
  status: JobStatus
  sizeBytes: number
  confidence: number | null
  engine: string | null
  extraction: Record<string, unknown> | null
  validation: { reviewRequired: boolean; issues: ValidationIssue[]; ruleVersion: string } | null
  error: string | null
  createdAt: string
  updatedAt: string
  latencyMs: number | null
}

export interface ValidationIssue { field: string; code: string; message: string; severity: 'BLOCK' | 'WARN' | 'INFO' }
export interface PageResponse<T> { content: T[]; totalElements: number; totalPages: number; number: number; size: number }
export interface DashboardData {
  total: number; queued: number; processing: number; pendingReview: number; completed: number; failed: number
  targets: Record<string, string>
}
export interface AuditEvent { id: string; action: string; actor: string; detail: string; createdAt: string }
