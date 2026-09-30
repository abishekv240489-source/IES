import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  TextField,
  Button,
  CircularProgress,
  Alert,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  IconButton,
  Stack,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SaveIcon from '@mui/icons-material/Save';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import DirectionsBoatIcon from '@mui/icons-material/DirectionsBoat';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import BusinessIcon from '@mui/icons-material/Business';
import { StatusChip } from '../components/StatusChip';

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [invoice, setInvoice] = useState<any>(null);
  const [formData, setFormData] = useState<any>({
    header: {
      invoiceNumber: '',
      invoiceDate: '',
      dueDate: '',
      currency: 'USD',
      poReference: '',
    },
    vendor: {
      name: '',
      address: '',
      country: '',
      taxRegistrationNumber: '',
      contact: '',
    },
    customer: {
      name: '',
      address: '',
      businessUnit: '',
      accountingReference: '',
    },
    vessel: {
      vesselName: '',
      voyage: '',
      imo: '',
      port: '',
    },
    bankDetails: {
      bankName: '',
      iban: '',
      swiftBic: '',
      accountNumber: '',
      beneficiary: '',
    },
    amounts: {
      subtotal: '0',
      discount: '0',
      tax: '0',
      shipping: '0',
      total: '0',
      exchangeRate: '',
    },
    lineItems: [],
  });

  const fetchInvoice = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`http://localhost:8080/api/v1/invoices/${id}`);
      if (!res.ok) throw new Error(`Failed to load invoice (${res.status})`);
      const data = await res.json();
      setInvoice(data);

      const inv = data.invoice || {};
      setFormData({
        header: {
          invoiceNumber: inv.header?.invoiceNumber?.value ?? '',
          invoiceDate: inv.header?.invoiceDate?.value ?? '',
          dueDate: inv.header?.dueDate?.value ?? '',
          currency: inv.header?.currency?.value ?? 'USD',
          poReference: inv.header?.poReference?.value ?? '',
        },
        vendor: {
          name: inv.vendor?.name?.value ?? '',
          address: inv.vendor?.address?.value ?? '',
          country: inv.vendor?.country?.value ?? '',
          taxRegistrationNumber: inv.vendor?.taxRegistrationNumber?.value ?? '',
          contact: inv.vendor?.contact?.value ?? '',
        },
        customer: {
          name: inv.customer?.name?.value ?? inv.billTo?.entity?.value ?? '',
          address: inv.customer?.address?.value ?? inv.billTo?.address?.value ?? '',
          businessUnit: inv.billTo?.businessUnit?.value ?? '',
          accountingReference: inv.billTo?.accountingReference?.value ?? '',
        },
        vessel: {
          vesselName: inv.vessel?.vesselName?.value ?? '',
          voyage: inv.vessel?.voyage?.value ?? '',
          imo: inv.vessel?.imo?.value ?? '',
          port: inv.vessel?.port?.value ?? '',
        },
        bankDetails: {
          bankName: inv.bankDetails?.bankName?.value ?? '',
          iban: inv.bankDetails?.iban?.value ?? '',
          swiftBic: inv.bankDetails?.swiftBic?.value ?? '',
          accountNumber: inv.bankDetails?.accountNumber?.value ?? '',
          beneficiary: inv.bankDetails?.beneficiary?.value ?? '',
        },
        amounts: {
          subtotal: inv.amounts?.subtotal?.value ?? '0',
          discount: inv.amounts?.discount?.value ?? '0',
          tax: inv.amounts?.tax?.value ?? '0',
          shipping: inv.amounts?.shipping?.value ?? '0',
          total: inv.amounts?.total?.value ?? '0',
          exchangeRate: inv.amounts?.exchangeRate?.value ?? '',
        },
        lineItems: Array.isArray(inv.lineItems)
          ? inv.lineItems.map((li: any) => ({
              description: li.description?.value ?? '',
              quantity: li.quantity?.value ?? '1',
              unitPrice: li.unitPrice?.value ?? '0',
              amount: li.amount?.value ?? '0',
              chargeCode: li.chargeCode?.value ?? '',
            }))
          : [],
      });
    } catch (err: any) {
      setError(err.message || 'Error loading invoice');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) fetchInvoice();
  }, [id]);

  const handleFieldChange = (section: string, field: string, value: string) => {
    setFormData((prev: any) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value,
      },
    }));
  };

  const handleLineItemChange = (index: number, field: string, value: string) => {
    setFormData((prev: any) => {
      const items = [...prev.lineItems];
      items[index] = { ...items[index], [field]: value };

      if (field === 'quantity' || field === 'unitPrice') {
        const qty = parseFloat(field === 'quantity' ? value : items[index].quantity) || 0;
        const up = parseFloat(field === 'unitPrice' ? value : items[index].unitPrice) || 0;
        items[index].amount = (qty * up).toFixed(2);
      }
      return { ...prev, lineItems: items };
    });
  };

  const handleAddLineItem = () => {
    setFormData((prev: any) => ({
      ...prev,
      lineItems: [
        ...prev.lineItems,
        { description: '', quantity: '1', unitPrice: '0', amount: '0', chargeCode: '' },
      ],
    }));
  };

  const handleDeleteLineItem = (index: number) => {
    setFormData((prev: any) => ({
      ...prev,
      lineItems: prev.lineItems.filter((_: any, i: number) => i !== index),
    }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      const payload = {
        header: {
          invoiceNumber: { value: formData.header.invoiceNumber, confidence: 1.0 },
          invoiceDate: { value: formData.header.invoiceDate, confidence: 1.0 },
          dueDate: { value: formData.header.dueDate || null, confidence: 1.0 },
          currency: { value: formData.header.currency, confidence: 1.0 },
          poReference: { value: formData.header.poReference || null, confidence: 1.0 },
        },
        vendor: {
          name: { value: formData.vendor.name, confidence: 1.0 },
          address: { value: formData.vendor.address || null, confidence: 1.0 },
          country: { value: formData.vendor.country || null, confidence: 1.0 },
          taxRegistrationNumber: { value: formData.vendor.taxRegistrationNumber || null, confidence: 1.0 },
          contact: { value: formData.vendor.contact || null, confidence: 1.0 },
        },
        customer: {
          name: { value: formData.customer.name || null, confidence: 1.0 },
          address: { value: formData.customer.address || null, confidence: 1.0 },
        },
        billTo: {
          entity: { value: formData.customer.name || null, confidence: 1.0 },
          address: { value: formData.customer.address || null, confidence: 1.0 },
          businessUnit: { value: formData.customer.businessUnit || null, confidence: 1.0 },
          accountingReference: { value: formData.customer.accountingReference || null, confidence: 1.0 },
        },
        vessel: {
          vesselName: { value: formData.vessel.vesselName || null, confidence: 1.0 },
          voyage: { value: formData.vessel.voyage || null, confidence: 1.0 },
          imo: { value: formData.vessel.imo || null, confidence: 1.0 },
          port: { value: formData.vessel.port || null, confidence: 1.0 },
        },
        amounts: {
          subtotal: { value: formData.amounts.subtotal, confidence: 1.0 },
          discount: { value: formData.amounts.discount, confidence: 1.0 },
          tax: { value: formData.amounts.tax, confidence: 1.0 },
          shipping: { value: formData.amounts.shipping, confidence: 1.0 },
          total: { value: formData.amounts.total, confidence: 1.0 },
          exchangeRate: { value: formData.amounts.exchangeRate || null, confidence: 1.0 },
        },
        bankDetails: {
          bankName: { value: formData.bankDetails.bankName || null, confidence: 1.0 },
          iban: { value: formData.bankDetails.iban || null, confidence: 1.0 },
          swiftBic: { value: formData.bankDetails.swiftBic || null, confidence: 1.0 },
          accountNumber: { value: formData.bankDetails.accountNumber || null, confidence: 1.0 },
          beneficiary: { value: formData.bankDetails.beneficiary || null, confidence: 1.0 },
        },
        lineItems: formData.lineItems.map((li: any) => ({
          description: { value: li.description, confidence: 1.0 },
          quantity: { value: li.quantity, confidence: 1.0 },
          unitPrice: { value: li.unitPrice, confidence: 1.0 },
          amount: { value: li.amount, confidence: 1.0 },
          chargeCode: { value: li.chargeCode || null, confidence: 1.0 },
        })),
      };

      const res = await fetch(`http://localhost:8080/api/v1/invoices/${id}/revision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ invoice: payload }),
      });

      if (!res.ok) {
        const fallbackRes = await fetch(`http://localhost:8080/api/v1/invoices/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ invoice: payload }),
        });
        if (!fallbackRes.ok) throw new Error('Failed to save invoice updates');
      }

      setSuccess('Invoice updates and maritime fields successfully saved!');
      fetchInvoice();
    } catch (err: any) {
      setError(err.message || 'Error saving invoice corrections');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Top Navigation & Action Bar */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Stack direction="row" spacing={2} alignItems="center">
          <IconButton onClick={() => navigate('/invoices')}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h5" fontWeight="bold">
            Invoice: {formData.header.invoiceNumber || invoice?.originalFilename || id}
          </Typography>
          {invoice?.status && <StatusChip status={invoice.status} />}
        </Stack>

        <Button
          variant="contained"
          color="primary"
          startIcon={saving ? <CircularProgress size={20} color="inherit" /> : <SaveIcon />}
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save Corrections'}
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Grid container spacing={3}>
        {/* Left Side: Document Preview */}
        <Grid item xs={12} md={5}>
          <Card sx={{ height: '85vh' }}>
            <CardContent sx={{ height: '100%', p: 0 }}>
              <iframe
                src={`http://localhost:8080/api/v1/invoices/${id}/source`}
                title="Invoice Source Document"
                width="100%"
                height="100%"
                style={{ border: 'none' }}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Right Side: Form Fields */}
        <Grid item xs={12} md={7}>
          <Stack spacing={3} sx={{ height: '85vh', overflowY: 'auto', pr: 1 }}>
            
            {/* Header Section */}
            <Card>
              <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                  <ReceiptLongIcon color="primary" fontSize="small" />
                  <Typography variant="subtitle1" fontWeight="bold">
                    Header Details
                  </Typography>
                </Stack>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={4}>
                    <TextField
                      label="Invoice Number"
                      fullWidth
                      size="small"
                      value={formData.header.invoiceNumber}
                      onChange={(e) => handleFieldChange('header', 'invoiceNumber', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField
                      label="Invoice Date"
                      type="date"
                      InputLabelProps={{ shrink: true }}
                      fullWidth
                      size="small"
                      value={formData.header.invoiceDate}
                      onChange={(e) => handleFieldChange('header', 'invoiceDate', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField
                      label="Due Date"
                      type="date"
                      InputLabelProps={{ shrink: true }}
                      fullWidth
                      size="small"
                      value={formData.header.dueDate}
                      onChange={(e) => handleFieldChange('header', 'dueDate', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      label="Currency"
                      fullWidth
                      size="small"
                      value={formData.header.currency}
                      onChange={(e) => handleFieldChange('header', 'currency', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      label="PO Reference"
                      placeholder="PO Number or Contract Ref"
                      fullWidth
                      size="small"
                      value={formData.header.poReference}
                      onChange={(e) => handleFieldChange('header', 'poReference', e.target.value)}
                    />
                  </Grid>
                </Grid>
              </CardContent>
            </Card>

            {/* Maritime & Vessel Details */}
            <Card sx={{ borderLeft: '4px solid #0288d1' }}>
              <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                  <DirectionsBoatIcon color="primary" fontSize="small" />
                  <Typography variant="subtitle1" fontWeight="bold">
                    Vessel / Shipping Information
                  </Typography>
                </Stack>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      label="Vessel Name"
                      placeholder="e.g. MV KOTA JAYA"
                      fullWidth
                      size="small"
                      value={formData.vessel.vesselName}
                      onChange={(e) => handleFieldChange('vessel', 'vesselName', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      label="Voyage Number"
                      placeholder="e.g. 024W"
                      fullWidth
                      size="small"
                      value={formData.vessel.voyage}
                      onChange={(e) => handleFieldChange('vessel', 'voyage', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      label="IMO Number"
                      placeholder="e.g. 9123456"
                      fullWidth
                      size="small"
                      value={formData.vessel.imo}
                      onChange={(e) => handleFieldChange('vessel', 'imo', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      label="Port of Call / Bunker Port"
                      placeholder="e.g. Singapore"
                      fullWidth
                      size="small"
                      value={formData.vessel.port}
                      onChange={(e) => handleFieldChange('vessel', 'port', e.target.value)}
                    />
                  </Grid>
                </Grid>
              </CardContent>
            </Card>

            {/* Bank Details & Remittance */}
            <Card sx={{ borderLeft: '4px solid #2e7d32' }}>
              <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                  <AccountBalanceIcon color="success" fontSize="small" />
                  <Typography variant="subtitle1" fontWeight="bold">
                    Bank & Remittance Details
                  </Typography>
                </Stack>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      label="Bank Name"
                      fullWidth
                      size="small"
                      value={formData.bankDetails.bankName}
                      onChange={(e) => handleFieldChange('bankDetails', 'bankName', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      label="Beneficiary Name"
                      fullWidth
                      size="small"
                      value={formData.bankDetails.beneficiary}
                      onChange={(e) => handleFieldChange('bankDetails', 'beneficiary', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField
                      label="Account Number"
                      fullWidth
                      size="small"
                      value={formData.bankDetails.accountNumber}
                      onChange={(e) => handleFieldChange('bankDetails', 'accountNumber', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField
                      label="SWIFT / BIC"
                      fullWidth
                      size="small"
                      value={formData.bankDetails.swiftBic}
                      onChange={(e) => handleFieldChange('bankDetails', 'swiftBic', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField
                      label="IBAN"
                      fullWidth
                      size="small"
                      value={formData.bankDetails.iban}
                      onChange={(e) => handleFieldChange('bankDetails', 'iban', e.target.value)}
                    />
                  </Grid>
                </Grid>
              </CardContent>
            </Card>

            {/* Vendor & Customer Entities */}
            <Card>
              <CardContent>
                <Stack direction="row" spacing={1} alignItems="center" mb={2}>
                  <BusinessIcon color="primary" fontSize="small" />
                  <Typography variant="subtitle1" fontWeight="bold">
                    Vendor & Bill-To Counterparties
                  </Typography>
                </Stack>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Vendor Details
                    </Typography>
                    <TextField
                      label="Vendor Name"
                      fullWidth
                      size="small"
                      value={formData.vendor.name}
                      onChange={(e) => handleFieldChange('vendor', 'name', e.target.value)}
                      sx={{ mb: 1.5 }}
                    />
                    <TextField
                      label="Tax Registration / VAT Number"
                      fullWidth
                      size="small"
                      value={formData.vendor.taxRegistrationNumber}
                      onChange={(e) => handleFieldChange('vendor', 'taxRegistrationNumber', e.target.value)}
                      sx={{ mb: 1.5 }}
                    />
                    <TextField
                      label="Country"
                      fullWidth
                      size="small"
                      value={formData.vendor.country}
                      onChange={(e) => handleFieldChange('vendor', 'country', e.target.value)}
                      sx={{ mb: 1.5 }}
                    />
                    <TextField
                      label="Vendor Address"
                      multiline
                      rows={2}
                      fullWidth
                      size="small"
                      value={formData.vendor.address}
                      onChange={(e) => handleFieldChange('vendor', 'address', e.target.value)}
                    />
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Bill-To / Customer Details
                    </Typography>
                    <TextField
                      label="Customer / Entity Name"
                      fullWidth
                      size="small"
                      value={formData.customer.name}
                      onChange={(e) => handleFieldChange('customer', 'name', e.target.value)}
                      sx={{ mb: 1.5 }}
                    />
                    <TextField
                      label="Business Unit"
                      fullWidth
                      size="small"
                      value={formData.customer.businessUnit}
                      onChange={(e) => handleFieldChange('customer', 'businessUnit', e.target.value)}
                      sx={{ mb: 1.5 }}
                    />
                    <TextField
                      label="Accounting / GL Reference"
                      fullWidth
                      size="small"
                      value={formData.customer.accountingReference}
                      onChange={(e) => handleFieldChange('customer', 'accountingReference', e.target.value)}
                      sx={{ mb: 1.5 }}
                    />
                    <TextField
                      label="Customer Address"
                      multiline
                      rows={2}
                      fullWidth
                      size="small"
                      value={formData.customer.address}
                      onChange={(e) => handleFieldChange('customer', 'address', e.target.value)}
                    />
                  </Grid>
                </Grid>
              </CardContent>
            </Card>

            {/* Line Items */}
            <Card>
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="subtitle1" fontWeight="bold">
                    Line Items
                  </Typography>
                  <Button
                    size="small"
                    startIcon={<AddCircleOutlineIcon />}
                    onClick={handleAddLineItem}
                  >
                    Add Line
                  </Button>
                </Stack>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell width="35%">Description</TableCell>
                      <TableCell width="15%">Charge Code</TableCell>
                      <TableCell width="12%">Qty</TableCell>
                      <TableCell width="18%">Unit Price</TableCell>
                      <TableCell width="15%">Total</TableCell>
                      <TableCell width="5%"></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {formData.lineItems.map((item: any, idx: number) => (
                      <TableRow key={idx}>
                        <TableCell>
                          <TextField
                            size="small"
                            fullWidth
                            value={item.description}
                            onChange={(e) => handleLineItemChange(idx, 'description', e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            fullWidth
                            placeholder="e.g. BUNKER"
                            value={item.chargeCode}
                            onChange={(e) => handleLineItemChange(idx, 'chargeCode', e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            fullWidth
                            value={item.quantity}
                            onChange={(e) => handleLineItemChange(idx, 'quantity', e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            fullWidth
                            value={item.unitPrice}
                            onChange={(e) => handleLineItemChange(idx, 'unitPrice', e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            fullWidth
                            value={item.amount}
                            onChange={(e) => handleLineItemChange(idx, 'amount', e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <IconButton size="small" onClick={() => handleDeleteLineItem(idx)}>
                            <DeleteOutlineIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            {/* Financial Amounts & Currency */}
            <Card>
              <CardContent>
                <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                  Amounts & Reconciliation
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6} sm={4}>
                    <TextField
                      label="Subtotal"
                      fullWidth
                      size="small"
                      value={formData.amounts.subtotal}
                      onChange={(e) => handleFieldChange('amounts', 'subtotal', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={6} sm={4}>
                    <TextField
                      label="Trade Discount"
                      fullWidth
                      size="small"
                      value={formData.amounts.discount}
                      onChange={(e) => handleFieldChange('amounts', 'discount', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={6} sm={4}>
                    <TextField
                      label="Tax / VAT"
                      fullWidth
                      size="small"
                      value={formData.amounts.tax}
                      onChange={(e) => handleFieldChange('amounts', 'tax', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={6} sm={4}>
                    <TextField
                      label="Shipping / Barge"
                      fullWidth
                      size="small"
                      value={formData.amounts.shipping}
                      onChange={(e) => handleFieldChange('amounts', 'shipping', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={6} sm={4}>
                    <TextField
                      label="Exchange Rate"
                      placeholder="e.g. 1.34"
                      fullWidth
                      size="small"
                      value={formData.amounts.exchangeRate}
                      onChange={(e) => handleFieldChange('amounts', 'exchangeRate', e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField
                      label="Net Total Amount"
                      fullWidth
                      size="small"
                      value={formData.amounts.total}
                      onChange={(e) => handleFieldChange('amounts', 'total', e.target.value)}
                    />
                  </Grid>
                </Grid>
              </CardContent>
            </Card>

          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
}
