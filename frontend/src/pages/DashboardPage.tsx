import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded'
import CheckCircleRounded from '@mui/icons-material/CheckCircleRounded'
import ErrorOutlineRounded from '@mui/icons-material/ErrorOutlineRounded'
import PendingActionsRounded from '@mui/icons-material/PendingActionsRounded'
import SpeedRounded from '@mui/icons-material/SpeedRounded'
import { Alert, Box, Button, Card, CardContent, CircularProgress, Grid2, LinearProgress, Stack, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getDashboard, getInvoices } from '../api'
import { StatusChip } from '../components/StatusChip'

export function DashboardPage() {
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: getDashboard, refetchInterval: 5000 })
  const invoices = useQuery({ queryKey: ['invoices', 'recent'], queryFn: () => getInvoices(), refetchInterval: 5000 })
  if (dashboard.isLoading) return <Box display="grid" minHeight="60vh" sx={{ placeItems: 'center' }}><CircularProgress /></Box>
  if (dashboard.isError) return <Alert severity="error">The API is not reachable. Start the Spring service with the local profile.</Alert>
  const data = dashboard.data!
  const cards = [
    { label: 'Invoices received', value: data.total, icon: <SpeedRounded />, tone: 'teal' },
    { label: 'Completed', value: data.completed, icon: <CheckCircleRounded />, tone: 'green' },
    { label: 'Awaiting review', value: data.pendingReview, icon: <PendingActionsRounded />, tone: 'amber' },
    { label: 'Failed', value: data.failed, icon: <ErrorOutlineRounded />, tone: 'red' },
  ]
  return <Stack spacing={3.2}>
    <Box className="page-heading"><Box><Typography variant="h1">Invoice operations</Typography><Typography color="text.secondary" mt={.7}>Track extraction health, clear exceptions and protect downstream finance workflows.</Typography></Box><Button component={Link} to="/submit" variant="contained" endIcon={<ArrowForwardRounded />}>Submit invoices</Button></Box>
    <Grid2 container spacing={2}>{cards.map(card => <Grid2 key={card.label} size={{ xs: 12, sm: 6, lg: 3 }}><Card><CardContent><Stack direction="row" justifyContent="space-between" alignItems="center"><Box><Typography variant="caption" color="text.secondary" fontWeight={750}>{card.label.toUpperCase()}</Typography><Typography fontSize="2rem" fontWeight={780} mt={.5}>{card.value}</Typography></Box><Box className={`metric-icon ${card.tone}`}>{card.icon}</Box></Stack></CardContent></Card></Grid2>)}</Grid2>
    <Grid2 container spacing={2.4}>
      <Grid2 size={{ xs: 12, lg: 8 }}><Card><CardContent sx={{ p: 3 }}><Stack direction="row" justifyContent="space-between" alignItems="center" mb={2.2}><Box><Typography variant="h2">Recent invoices</Typography><Typography variant="body2" color="text.secondary">Latest processing activity</Typography></Box><Button component={Link} to="/invoices">View all</Button></Stack><Stack divider={<Box className="divider" />}>
        {(invoices.data?.content || []).slice(0, 6).map(job => <Stack key={job.id} component={Link} to={`/invoices/${job.id}`} className="invoice-row" direction="row" alignItems="center" justifyContent="space-between"><Box minWidth={0}><Typography fontWeight={720} noWrap>{job.filename}</Typography><Typography variant="caption" color="text.secondary">{new Date(job.createdAt).toLocaleString()} · {job.engine || 'Waiting for worker'}</Typography></Box><Stack direction="row" spacing={2} alignItems="center"><Typography variant="body2" color="text.secondary">{job.confidence == null ? '—' : `${Math.round(job.confidence * 100)}%`}</Typography><StatusChip status={job.status} /></Stack></Stack>)}
        {!invoices.data?.content.length && <Box py={6} textAlign="center"><Typography color="text.secondary">No invoices yet. Submit a batch to begin.</Typography></Box>}
      </Stack></CardContent></Card></Grid2>
      <Grid2 size={{ xs: 12, lg: 4 }}><Card className="target-card"><CardContent sx={{ p: 3 }}><Typography variant="h2">Acceptance targets</Typography><Typography variant="body2" color="text.secondary" mt={.5} mb={2.5}>Measured against a frozen, labelled holdout set.</Typography>{Object.entries(data.targets).filter(([key]) => key !== 'status').map(([key, value]) => <Box key={key} mb={2.2}><Stack direction="row" justifyContent="space-between" mb={.7}><Typography variant="body2" fontWeight={700}>{key.replace(/([A-Z])/g, ' $1')}</Typography><Typography variant="body2" color="primary.main" fontWeight={800}>{value}</Typography></Stack><LinearProgress variant="determinate" value={0} sx={{ height: 7, borderRadius: 5, bgcolor: '#e7edef' }} /></Box>)}<Alert severity="info" sx={{ mt: 3 }}>Targets are not marked complete until benchmark evidence exists.</Alert></CardContent></Card></Grid2>
    </Grid2>
  </Stack>
}
