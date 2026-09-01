export const JOB_STATUSES = [
  'QUEUED',
  'PREPROCESSING',
  'OCR_RUNNING',
  'MAPPING',
  'VALIDATING',
  'PENDING_REVIEW',
  'COMPLETED',
  'FAILED',
  'REJECTED',
] as const

export type JobStatus = (typeof JOB_STATUSES)[number]

export interface ExtractedField {
  value: unknown
  confidence: number
  source?: string
  page?: number | null
}

export interface ValidationIssue {
  field: string
  code: string
  message: string
  severity: 'BLOCK' | 'WARN' | 'INFO'
}

export interface ValidationResult {
  reviewRequired: boolean
  issues: ValidationIssue[]
  ruleVersion: string
}

export interface AiExtractionResponse {
  document_id: string
  invoice: Record<string, unknown>
  overall_confidence: number
  engine: string
  ocr_pages: number
  processing_ms: number
  warnings: string[]
}
