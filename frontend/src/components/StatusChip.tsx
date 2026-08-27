import { Chip } from '@mui/material'
import type { JobStatus } from '../types'

const styles: Record<JobStatus, { bg: string; color: string; label: string }> = {
  QUEUED: { bg: '#edf1f2', color: '#53666c', label: 'Queued' },
  PREPROCESSING: { bg: '#e7f0ff', color: '#315d96', label: 'Preparing' },
  OCR_RUNNING: { bg: '#e7f0ff', color: '#315d96', label: 'OCR running' },
  MAPPING: { bg: '#ede9ff', color: '#5b47a3', label: 'Mapping' },
  VALIDATING: { bg: '#ede9ff', color: '#5b47a3', label: 'Validating' },
  PENDING_REVIEW: { bg: '#fff2d9', color: '#945c04', label: 'Needs review' },
  COMPLETED: { bg: '#def4ea', color: '#146d50', label: 'Completed' },
  FAILED: { bg: '#fde5e6', color: '#a52d32', label: 'Failed' },
  REJECTED: { bg: '#f1e8e8', color: '#6d4242', label: 'Rejected' },
}

export function StatusChip({ status }: { status: JobStatus }) {
  const style = styles[status]
  return <Chip size="small" label={style.label} sx={{ bgcolor: style.bg, color: style.color, borderRadius: 1.5 }} />
}
