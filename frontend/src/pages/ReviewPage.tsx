import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react'
import ArrowBackRounded from '@mui/icons-material/ArrowBackRounded'
import CheckRounded from '@mui/icons-material/CheckRounded'
import CloseRounded from '@mui/icons-material/CloseRounded'
import DescriptionRounded from '@mui/icons-material/DescriptionRounded'
import DownloadRounded from '@mui/icons-material/DownloadRounded'
import HistoryRounded from '@mui/icons-material/HistoryRounded'
import OpenInNewRounded from '@mui/icons-material/OpenInNewRounded'
import SearchRounded from '@mui/icons-material/SearchRounded'
import VisibilityOffRounded from '@mui/icons-material/VisibilityOffRounded'
import VisibilityRounded from '@mui/icons-material/VisibilityRounded'
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider, FormControl, Grid2, InputAdornment, InputLabel, MenuItem, Select, Stack, TextField, Tooltip, Typography } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getBatchAuditUrl, getEvents, getInvoice, getInvoiceAuditUrl, getInvoiceSourceUrl, reviewInvoice } from '../api'
import { StatusChip } from '../components/StatusChip'
import type { ExtractedField } from '../types'

interface FlatField { path: string[]; label: string; field: ExtractedField }
interface FieldSection { key: string; label: string; fields: FlatField[]; sop: boolean }

const SOP_SECTIONS = [
  { key: 'header', label: 'Header' },
  { key: 'vendor', label: 'Vendor' },
  { key: 'billTo', label: 'Bill To' },
  { key: 'vessel', label: 'Vessel' },
  { key: 'amounts', label: 'Amounts' },
  { key: 'bankDetails', label: 'Bank Details' },
  { key: 'lineItems', label: 'Line Items' },
] as const

const SOP_SECTION_KEYS = new Set<string>(SOP_SECTIONS.map(({ key }) => key))

function humanize(value: string) {
  return value.replace(/([a-z0-9])([A-Z])/g, '$1 $2').replaceAll('_', ' ').replace(/^./, (character) => character.toUpperCase())
}

function fieldLabel(path: string[]) {
  const fieldPath = path.slice(1)
  if (!fieldPath.length) return humanize(path.at(-1) || 'Field')
  return fieldPath.map((part) => /^\d+$/.test(part) ? `Line ${Number(part) + 1}` : humanize(part)).join(' / ')
}

function fieldsOf(value: unknown, path: string[] = []): FlatField[] {
  if (!value || typeof value !== 'object') return []
  if ('value' in value && 'confidence' in value) return [{ path, label: fieldLabel(path), field: value as ExtractedField }]
  return Object.entries(value as Record<string, unknown>).flatMap(([key, nested]) => fieldsOf(nested, [...path, key]))
}

function sectionsOf(value: Record<string, unknown> | null): FieldSection[] {
  if (!value) return []
  const sections: FieldSection[] = SOP_SECTIONS.map(({ key, label }) => ({ key, label, fields: fieldsOf(value[key], [key]), sop: true }))
    .filter(({ fields }) => fields.length)
  const extensionFields = Object.entries(value)
    .filter(([key]) => !SOP_SECTION_KEYS.has(key))
    .flatMap(([key, nested]) => fieldsOf(nested, [key]))
  if (extensionFields.length) sections.push({ key: 'additional', label: 'Additional fields', fields: extensionFields, sop: false })
  return sections
}

function setAt(root: Record<string, unknown>, path: string[], value: string) {
  const copy = structuredClone(root)
  let cursor: Record<string, unknown> = copy
  path.slice(0, -1).forEach(key => { cursor = cursor[key] as Record<string, unknown> })
  const current = cursor[path.at(-1)!] as ExtractedField
  cursor[path.at(-1)!] = { ...current, value, source: 'review', confidence: 1 }
  return copy
}

function SourcePreview({ filename, url }: { filename: string; url: string }) {
  const extension = filename.split('.').pop()?.toLowerCase()
  if (['png', 'jpg', 'jpeg'].includes(extension || '')) {
    return <Box component="img" src={url} alt={`Source invoice ${filename}`} className="source-image" />
  }
  if (['tif', 'tiff'].includes(extension || '')) {
    return <Box className="source-fallback"><DescriptionRounded /><Typography variant="h2">TIFF preview is not supported by this browser</Typography><Typography color="text.secondary">Open the source file in a compatible viewer.</Typography><Button component="a" href={url} target="_blank" rel="noreferrer" variant="contained" endIcon={<OpenInNewRounded />}>Open source</Button></Box>
  }
  return <Box component="iframe" src={url} title={`Source invoice ${filename}`} className="source-frame" />
}

export function ReviewPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const client = useQueryClient()
  const splitRef = useRef<HTMLDivElement>(null)
  const query = useQuery({ queryKey: ['invoice', id], queryFn: () => getInvoice(id), refetchInterval: data => ['QUEUED','PREPROCESSING','OCR_RUNNING','MAPPING','VALIDATING'].includes(data.state.data?.status || '') ? 2500 : false })
  const events = useQuery({ queryKey: ['events', id], queryFn: () => getEvents(id) })
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null)
  const [remarks, setRemarks] = useState('')
  const [sourceVisible, setSourceVisible] = useState(true)
  const [sourceWidth, setSourceWidth] = useState(46)
  const [fieldSearch, setFieldSearch] = useState('')
  const [sectionFilter, setSectionFilter] = useState('all')

  useEffect(() => { if (query.data?.extraction) setDraft(structuredClone(query.data.extraction)) }, [query.data?.extraction])

  const sections = useMemo(() => sectionsOf(draft), [draft])
  const filteredSections = useMemo(() => {
    const search = fieldSearch.trim().toLocaleLowerCase()
    return sections
      .filter(({ key }) => sectionFilter === 'all' || key === sectionFilter)
      .map((section) => ({
        ...section,
        fields: section.fields.filter(({ label, path }) => !search || label.toLocaleLowerCase().includes(search) || path.join('.').toLocaleLowerCase().includes(search)),
      }))
      .filter(({ fields }) => fields.length)
  }, [fieldSearch, sectionFilter, sections])
  const visibleFieldCount = filteredSections.reduce((total, section) => total + section.fields.length, 0)

  const mutation = useMutation({ mutationFn: (approved: boolean) => reviewInvoice(id, draft!, approved, remarks), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['invoices'] }); navigate('/invoices') } })

  const beginResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    const resize = (pointerEvent: PointerEvent) => {
      const bounds = splitRef.current?.getBoundingClientRect()
      if (!bounds) return
      setSourceWidth(Math.min(68, Math.max(28, ((pointerEvent.clientX - bounds.left) / bounds.width) * 100)))
    }
    const finish = () => {
      window.removeEventListener('pointermove', resize)
      window.removeEventListener('pointerup', finish)
    }
    window.addEventListener('pointermove', resize)
    window.addEventListener('pointerup', finish)
  }

  const resizeWithKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    setSourceWidth((width) => Math.min(68, Math.max(28, width + (event.key === 'ArrowLeft' ? -4 : 4))))
  }

  if (query.isLoading) return <Box display="grid" minHeight="60vh" sx={{ placeItems: 'center' }}><CircularProgress /></Box>
  if (!query.data) return <Alert severity="error">Invoice not found.</Alert>
  const job = query.data
  const inProgress = ['QUEUED','PREPROCESSING','OCR_RUNNING','MAPPING','VALIDATING'].includes(job.status)
  const batchAuditReady = ['COMPLETED', 'COMPLETED_WITH_ERRORS'].includes(job.batchStatus)
  const sourceUrl = getInvoiceSourceUrl(id)
  const invoiceAuditUrl = getInvoiceAuditUrl(id)
  const batchAuditUrl = getBatchAuditUrl(job.batchId)

  return <Stack spacing={2.5}>
    <Box>
      <Button component={Link} to="/invoices" startIcon={<ArrowBackRounded />} color="inherit">Back to invoices</Button>
      <Box className="page-heading" mt={1}>
        <Box minWidth={0}>
          <Stack direction="row" alignItems="center" spacing={1.5}><Typography variant="h1" noWrap>{job.filename}</Typography><StatusChip status={job.status}/></Stack>
          <Typography color="text.secondary" mt={.6}>Job {job.id} · {job.engine || 'Awaiting extraction worker'}</Typography>
        </Box>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          {!sourceVisible && <Button variant="outlined" startIcon={<VisibilityRounded />} onClick={() => setSourceVisible(true)}>Show source</Button>}
          <Button component="a" href={invoiceAuditUrl} disabled={inProgress} variant="outlined" startIcon={<DownloadRounded />}>Invoice audit</Button>
          <Tooltip title={batchAuditReady ? 'Download all invoices in this completed batch' : 'Available after every invoice in the batch finishes'}>
            <span><Button component="a" href={batchAuditUrl} disabled={!batchAuditReady} variant="contained" startIcon={<DownloadRounded />}>Batch audit</Button></span>
          </Tooltip>
        </Stack>
      </Box>
    </Box>
    {inProgress && <Alert severity="info">Processing is active. This page refreshes automatically.</Alert>}
    {job.error && <Alert severity="error">{job.error}</Alert>}

    <Box ref={splitRef} className={`review-split ${sourceVisible ? '' : 'source-hidden'}`}>
      {sourceVisible && <Card className="source-pane" sx={{ width: `${sourceWidth}%` }}>
        <Box className="pane-header"><Box><Typography variant="h2">Source invoice</Typography><Typography variant="body2" color="text.secondary">Drag the divider to resize the preview.</Typography></Box><Stack direction="row" spacing={.5}><Tooltip title="Open source in a new tab"><Button component="a" href={sourceUrl} target="_blank" rel="noreferrer" size="small" startIcon={<OpenInNewRounded />}>Open</Button></Tooltip><Button size="small" color="inherit" startIcon={<VisibilityOffRounded />} onClick={() => setSourceVisible(false)}>Hide</Button></Stack></Box>
        <Box className="source-preview"><SourcePreview filename={job.filename} url={sourceUrl} /></Box>
      </Card>}

      {sourceVisible && <Box role="separator" aria-label="Resize source invoice preview" aria-orientation="vertical" aria-valuemin={28} aria-valuemax={68} aria-valuenow={Math.round(sourceWidth)} tabIndex={0} className="review-divider" onPointerDown={beginResize} onKeyDown={resizeWithKeyboard}><Box /></Box>}

      <Card className="fields-pane"><CardContent className="fields-content">
        <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" spacing={2} mb={2}><Box><Typography variant="h2">Extracted fields</Typography><Typography variant="body2" color="text.secondary">Grouped by the SOP ParseJSON structure.</Typography></Box><Box textAlign={{ xs: 'left', md: 'right' }}><Typography variant="caption" color="text.secondary">OVERALL CONFIDENCE</Typography><Typography fontSize="1.4rem" fontWeight={780} color={(job.confidence || 0) >= .7 ? 'success.main' : 'warning.main'}>{job.confidence == null ? '—' : `${Math.round(job.confidence * 100)}%`}</Typography></Box></Stack>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} mb={1.5}>
          <TextField fullWidth size="small" label="Search extracted fields" placeholder="e.g. address, currency, amount" value={fieldSearch} onChange={(event) => setFieldSearch(event.target.value)} slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment> } }} />
          <FormControl size="small" sx={{ minWidth: { xs: '100%', md: 210 } }}><InputLabel id="section-filter-label">Section</InputLabel><Select labelId="section-filter-label" value={sectionFilter} label="Section" onChange={(event) => setSectionFilter(event.target.value)}><MenuItem value="all">All sections</MenuItem>{sections.map(({ key, label }) => <MenuItem key={key} value={key}>{label}</MenuItem>)}</Select></FormControl>
        </Stack>
        <Typography variant="caption" color="text.secondary" mb={1.5}>{visibleFieldCount} {visibleFieldCount === 1 ? 'field' : 'fields'} across {filteredSections.length} {filteredSections.length === 1 ? 'section' : 'sections'}</Typography>
        <Divider />
        <Box className="fields-scroll">
          {!sections.length ? <Box py={7} textAlign="center"><Typography color="text.secondary">Extraction fields will appear when processing completes.</Typography></Box> : !filteredSections.length ? <Box py={7} textAlign="center"><SearchRounded color="disabled" sx={{ fontSize: 42, mb: 1 }} /><Typography fontWeight={750}>No matching fields</Typography><Typography color="text.secondary">Try another field name or select a different section.</Typography></Box> : <Stack spacing={2}>{filteredSections.map((section) => <Box component="section" className="field-section" key={section.key} aria-labelledby={`section-${section.key}`}><Stack direction="row" alignItems="center" justifyContent="space-between" mb={1.5}><Stack direction="row" alignItems="center" spacing={1}><Typography id={`section-${section.key}`} variant="h3">{section.label}</Typography><Chip size="small" variant="outlined" label={section.sop ? `ParseJSON: ${section.key}` : 'Extension'} /></Stack><Typography variant="caption" color="text.secondary">{section.fields.length} {section.fields.length === 1 ? 'field' : 'fields'}</Typography></Stack><Grid2 container spacing={1.5}>{section.fields.map(({ path, label, field }) => <Grid2 key={path.join('.')} size={{ xs: 12, md: 6 }}><Box className={`field-card ${field.confidence < .7 ? 'low' : ''}`}><Stack direction="row" justifyContent="space-between" mb={.7}><Typography variant="caption" fontWeight={750} color="text.secondary">{label.toUpperCase()}</Typography><Typography variant="caption" fontWeight={800} color={field.confidence < .7 ? 'warning.main' : 'success.main'}>{Math.round(field.confidence * 100)}%</Typography></Stack><TextField variant="standard" fullWidth value={field.value ?? ''} disabled={job.status !== 'PENDING_REVIEW'} onChange={event => setDraft(current => current ? setAt(current, path, event.target.value) : current)} slotProps={{ input: { disableUnderline: job.status !== 'PENDING_REVIEW' } }} /><Typography variant="caption" color="text.secondary">Source: {field.source || 'unknown'}{field.page ? ` · Page ${field.page}` : ''}</Typography></Box></Grid2>)}</Grid2></Box>)}</Stack>}
        </Box>
      </CardContent></Card>
    </Box>

    <Grid2 container spacing={2.4}>
      <Grid2 size={{ xs: 12, lg: 6 }}><Card sx={{ height: '100%' }}><CardContent sx={{ p: 3 }}><Typography variant="h2">Validation</Typography><Typography variant="body2" color="text.secondary" mb={2}>Rule set {job.validation?.ruleVersion || '—'}</Typography>{job.validation?.issues?.length ? <Stack spacing={1}>{job.validation.issues.map((issue, index) => <Alert key={`${issue.code}-${index}`} severity={issue.severity === 'BLOCK' ? 'error' : 'warning'}><Typography variant="body2" fontWeight={750}>{issue.code.replaceAll('_', ' ')}</Typography><Typography variant="caption">{issue.message}</Typography></Alert>)}</Stack> : <Alert severity="success">No validation exceptions recorded.</Alert>}
        {job.status === 'PENDING_REVIEW' && <Box mt={2.5}><TextField multiline rows={3} fullWidth label="Review remarks" value={remarks} onChange={event => setRemarks(event.target.value)} /><Stack direction="row" spacing={1.2} mt={1.5}><Button fullWidth variant="outlined" color="error" startIcon={<CloseRounded />} disabled={mutation.isPending} onClick={() => mutation.mutate(false)}>Reject</Button><Button fullWidth variant="contained" startIcon={<CheckRounded />} disabled={mutation.isPending} onClick={() => mutation.mutate(true)}>Approve</Button></Stack></Box>}
      </CardContent></Card></Grid2>
      <Grid2 size={{ xs: 12, lg: 6 }}><Card sx={{ height: '100%' }}><CardContent sx={{ p: 3 }}><Stack direction="row" spacing={1} alignItems="center" mb={2}><HistoryRounded color="primary"/><Typography variant="h2">Audit trail</Typography></Stack><Stack spacing={1.8}>{events.data?.map(event => <Box key={event.id} className="audit-event"><Typography variant="body2" fontWeight={750}>{event.action.replaceAll('_', ' ')}</Typography><Typography variant="caption" color="text.secondary">{new Date(event.createdAt).toLocaleString()} · {event.actor}</Typography><Typography variant="body2" color="text.secondary" mt={.4}>{event.detail}</Typography></Box>)}</Stack></CardContent></Card></Grid2>
    </Grid2>
  </Stack>
}
