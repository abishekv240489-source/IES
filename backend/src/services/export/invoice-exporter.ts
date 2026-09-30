export interface ExportFlattenedRow {
  invoiceNumber: string;
  invoiceDate: string;
  dueDate: string;
  currency: string;
  poReference: string;
  vendorName: string;
  vendorTaxId: string;
  vendorCountry: string;
  customerName: string;
  businessUnit: string;
  vesselName: string;
  voyage: string;
  imo: string;
  port: string;
  bankName: string;
  iban: string;
  swiftBic: string;
  accountNumber: string;
  itemDescription: string;
  chargeCode: string;
  quantity: string;
  unitPrice: string;
  lineAmount: string;
  subtotal: string;
  discount: string;
  tax: string;
  totalAmount: string;
}

export function flattenInvoiceForCsv(invoiceJob: any): ExportFlattenedRow[] {
  const inv = invoiceJob.invoice || {};
  const rows: ExportFlattenedRow[] = [];

  const lineItems = Array.isArray(inv.lineItems) && inv.lineItems.length > 0
    ? inv.lineItems
    : [{ description: {}, quantity: {}, unitPrice: {}, amount: {}, chargeCode: {} }];

  for (const item of lineItems) {
    rows.push({
      invoiceNumber: inv.header?.invoiceNumber?.value ?? '',
      invoiceDate: inv.header?.invoiceDate?.value ?? '',
      dueDate: inv.header?.dueDate?.value ?? '',
      currency: inv.header?.currency?.value ?? 'USD',
      poReference: inv.header?.poReference?.value ?? '',
      vendorName: inv.vendor?.name?.value ?? '',
      vendorTaxId: inv.vendor?.taxRegistrationNumber?.value ?? '',
      vendorCountry: inv.vendor?.country?.value ?? '',
      customerName: inv.customer?.name?.value ?? inv.billTo?.entity?.value ?? '',
      businessUnit: inv.billTo?.businessUnit?.value ?? '',
      vesselName: inv.vessel?.vesselName?.value ?? '',
      voyage: inv.vessel?.voyage?.value ?? '',
      imo: inv.vessel?.imo?.value ?? '',
      port: inv.vessel?.port?.value ?? '',
      bankName: inv.bankDetails?.bankName?.value ?? '',
      iban: inv.bankDetails?.iban?.value ?? '',
      swiftBic: inv.bankDetails?.swiftBic?.value ?? '',
      accountNumber: inv.bankDetails?.accountNumber?.value ?? '',
      itemDescription: item.description?.value ?? '',
      chargeCode: item.chargeCode?.value ?? '',
      quantity: item.quantity?.value ?? '1',
      unitPrice: item.unitPrice?.value ?? '0',
      lineAmount: item.amount?.value ?? '0',
      subtotal: inv.amounts?.subtotal?.value ?? '0',
      discount: inv.amounts?.discount?.value ?? '0',
      tax: inv.amounts?.tax?.value ?? '0',
      totalAmount: inv.amounts?.total?.value ?? '0',
    });
  }

  return rows;
}

export function rowsToCsvString(rows: ExportFlattenedRow[]): string {
  const firstRow = rows[0];
  if (!firstRow) return '';

  const headers = Object.keys(firstRow) as (keyof ExportFlattenedRow)[];
  
  const escapeCell = (val: string) => {
    const clean = String(val ?? '').replace(/"/g, '""');
    return `"${clean}"`;
  };

  const headerLine = headers.map(escapeCell).join(',');
  const lines = rows.map((r) => headers.map((h) => escapeCell(r[h])).join(','));

  return [headerLine, ...lines].join('\r\n');
}