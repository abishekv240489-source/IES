import { useEffect, useMemo, useState } from 'react'
import ArrowBackRounded from '@mui/icons-material/ArrowBackRounded'
import CheckRounded from '@mui/icons-material/CheckRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import HistoryRounded from '@mui/icons-material/HistoryRounded'
import { Alert, Box, Button, Card, CardContent, CircularProgress, Divider, Grid2, LinearProgress, Stack, TextField, Typography } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getEvents, getInvoice, reviewInvoice } from '../api'
import { StatusChip } from '../components/StatusChip'
import type { ExtractedField } from '../types'

interface FlatField { path: string[]; label: string; field: ExtractedField }

function fieldsOf(value: unknown, path: string[] = []): FlatField[] {
  if (!value || typeof value !== 'object') return []
  if ('value' in value && 'confidence' in value) return [{ path, label: path.map(part => part.replace(/([A-Z])/g, ' $1')).join(' / '), field: value as ExtractedField }]
  return Object.entries(value as Record<string, unknown>).flatMap(([key, nested]) => fieldsOf(nested, [...path, key]))
}

function setAt(root: Record<string, unknown>, path: string[], value: string) {
  const copy = structuredClone(root)
  let cursor: Record<string, unknown> = copy
  path.slice(0, -1).forEach(key => { cursor = cursor[key] as Record<string, unknown> })
  const current = cursor[path.at(-1)!] as ExtractedField
  cursor[path.at(-1)!] = { ...current, value, source: 'review', confidence: 1 }
  return copy
}

export function ReviewPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['invoice', id], queryFn: () => getInvoice(id), refetchInterval: data => ['QUEUED','PREPROCESSING','OCR_RUNNING','MAPPING','VALIDATING'].includes(data.state.data?.status || '') ? 2500 : false })
  const events = useQuery({ queryKey: ['events', id], queryFn: () => getEvents(id) })
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null)
  const [remarks, setRemarks] = useState('')
  useEffect(() => { if (query.data?.extraction) setDraft(structuredClone(query.data.extraction)) }, [query.data?.extraction])
  const fields = useMemo(() => fieldsOf(draft), [draft])
  const mutation = useMutation({ mutationFn: (approved: boolean) => reviewInvoice(id, draft!, approved, remarks), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['invoices'] }); navigate('/invoices') } })
  if (query.isLoading) return <Box display="grid" minHeight="60vh" sx={{ placeItems: 'center' }}><CircularProgress /></Box>
  if (!query.data) return <Alert severity="error">Invoice not found.</Alert>
  const job = query.data
  const inProgress = ['QUEUED','PREPROCESSING','OCR_RUNNING','MAPPING','VALIDATING'].includes(job.status)
  return <Stack spacing={2.5}>
    <Box><Button component={Link} to="/invoices" startIcon={<ArrowBackRounded />} color="inherit">Back to invoices</Button><Box className="page-heading" mt={1}><Box minWidth={0}><Stack direction="row" alignItems="center" spacing={1.5}><Typography variant="h1" noWrap>{job.filename}</Typography><StatusChip status={job.status}/></Stack><Typography color="text.secondary" mt={.6}>Job {job.id} · {job.engine || 'Awaiting extraction worker'}</Typography></Box></Box></Box>
    {inProgress && <Alert severity="info">Processing is active. This page refreshes automatically.<LinearProgress sx={{ mt: 1.5 }} /></Alert>}
    {job.error && <Alert severity="error">{job.error}</Alert>}
    <Grid2 container spacing={2.4}>
      <Grid2 size={{ xs: 12, lg: 8 }}><Card><CardContent sx={{ p: 3 }}><Stack direction="row" justifyContent="space-between" mb={2}><Box><Typography variant="h2">Extracted fields</Typography><Typography variant="body2" color="text.secondary">Review low-confidence values before approval.</Typography></Box><Box textAlign="right"><Typography variant="caption" color="text.secondary">OVERALL CONFIDENCE</Typography><Typography fontSize="1.4rem" fontWeight={780} color={(job.confidence || 0) >= .7 ? 'success.main' : 'warning.main'}>{job.confidence == null ? '—' : `${Math.round(job.confidence * 100)}%`}</Typography></Box></Stack><Divider sx={{ mb: 1 }} />
        {!fields.length ? <Box py={7} textAlign="center"><Typography color="text.secondary">Extraction fields will appear when processing completes.</Typography></Box> : <Grid2 container spacing={1.5}>{fields.map(({ path, label, field }) => <Grid2 key={path.join('.')} size={{ xs: 12, md: 6 }}><Box className={`field-card ${field.confidence < .7 ? 'low' : ''}`}><Stack direction="row" justifyContent="space-between" mb={.7}><Typography variant="caption" fontWeight={750} color="text.secondary">{label.toUpperCase()}</Typography><Typography variant="caption" fontWeight={800} color={field.confidence < .7 ? 'warning.main' : 'success.main'}>{Math.round(field.confidence * 100)}%</Typography></Stack><TextField variant="standard" fullWidth value={field.value ?? ''} disabled={job.status !== 'PENDING_REVIEW'} onChange={event => setDraft(current => current ? setAt(current, path, event.target.value) : current)} slotProps={{ input: { disableUnderline: job.status !== 'PENDING_REVIEW' } }} /><Typography variant="caption" color="text.secondary">Source: {field.source || 'unknown'}</Typography></Box></Grid2>)}</Grid2>}
      </CardContent></Card></Grid2>
      <Grid2 size={{ xs: 12, lg: 4 }}><Stack spacing={2.4}>
        <Card><CardContent sx={{ p: 3 }}><Typography variant="h2">Validation</Typography><Typography variant="body2" color="text.secondary" mb={2}>Rule set {job.validation?.ruleVersion || '—'}</Typography>{job.validation?.issues?.length ? <Stack spacing={1}>{job.validation.issues.map((issue, index) => <Alert key={`${issue.code}-${index}`} severity={issue.severity === 'BLOCK' ? 'error' : 'warning'}><Typography variant="body2" fontWeight={750}>{issue.code.replaceAll('_', ' ')}</Typography><Typography variant="caption">{issue.message}</Typography></Alert>)}</Stack> : <Alert severity="success">No validation exceptions recorded.</Alert>}
          {job.status === 'PENDING_REVIEW' && <Box mt={2.5}><TextField multiline rows={3} fullWidth label="Review remarks" value={remarks} onChange={event => setRemarks(event.target.value)} /><Stack direction="row" spacing={1.2} mt={1.5}><Button fullWidth variant="outlined" color="error" startIcon={<CloseRounded />} disabled={mutation.isPending} onClick={() => mutation.mutate(false)}>Reject</Button><Button fullWidth variant="contained" startIcon={<CheckRounded />} disabled={mutation.isPending} onClick={() => mutation.mutate(true)}>Approve</Button></Stack></Box>}
        </CardContent></Card>
        <Card><CardContent sx={{ p: 3 }}><Stack direction="row" spacing={1} alignItems="center" mb={2}><HistoryRounded color="primary"/><Typography variant="h2">Audit trail</Typography></Stack><Stack spacing={1.8}>{events.data?.map(event => <Box key={event.id} className="audit-event"><Typography variant="body2" fontWeight={750}>{event.action.replaceAll('_', ' ')}</Typography><Typography variant="caption" color="text.secondary">{new Date(event.createdAt).toLocaleString()} · {event.actor}</Typography><Typography variant="body2" color="text.secondary" mt={.4}>{event.detail}</Typography></Box>)}</Stack></CardContent></Card>
      </Stack></Grid2>
    </Grid2>
  </Stack>
}
