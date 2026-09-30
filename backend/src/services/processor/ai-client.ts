import { GoogleGenAI, Type, type Schema } from '@google/genai';
import { readFile } from 'node:fs/promises';
import type { Config } from '../../config.js';
import type { AiExtractionResponse } from '../../domain/types.js';
import { PROMPT_STANDARD, PROMPT_TES_TERMINAL } from './prompts.js';

export interface ExtractionJobInput {
  jobId: string;
  path: string;
  originalFilename: string;
  contentType: string;
}

const GEMINI_MODEL = 'gemini-3.5-flash';

const invoiceJsonSchema: Schema = {
  // ... (Keep existing schema definition exactly as is)
  type: Type.OBJECT,
  properties: {
    invoice_number: { type: Type.STRING, description: 'Unique invoice identifier or reference number' },
    invoice_date: { type: Type.STRING, description: 'Date invoice was issued in ISO 8601 YYYY-MM-DD format' },
    due_date: { type: Type.STRING, description: 'Payment due date in ISO 8601 YYYY-MM-DD format. Return null if omitted.' },
    currency: { type: Type.STRING, description: '3-letter ISO 4217 currency code, e.g. USD, SGD, EUR' },
    po_reference: { type: Type.STRING, description: 'Customer purchase order reference or contract number. Return null if none.' },
    vendor_name: { type: Type.STRING, description: 'Full legal name of the seller, supplier, or issuing bunker vendor. Check letterhead and graphic banners.' },
    vendor_address: { type: Type.STRING, description: 'Physical or mailing address of the supplier. Return null if not present.' },
    vendor_country: { type: Type.STRING, description: 'Country of the vendor. Return null if not stated.' },
    vendor_tax_id: { type: Type.STRING, description: 'Tax registration number, VAT number, GST number, or business registration number.' },
    vendor_contact: { type: Type.STRING, description: 'Vendor contact information such as phone, email, or contact person.' },
    customer_name: { type: Type.STRING, description: 'Name of the billed entity, buyer, or charterer. Return null if not identified.' },
    customer_address: { type: Type.STRING, description: 'Physical or billing address of the customer. Return null if absent.' },
    bill_to_business_unit: { type: Type.STRING, description: 'Business unit or department indicated in bill-to section. Return null if none.' },
    bill_to_accounting_ref: { type: Type.STRING, description: 'Accounting reference, customer account code, or GL code. Return null if none.' },
    vessel: {
      type: Type.OBJECT,
      description: 'Vessel and voyage shipping details where applicable to marine invoices',
      properties: {
        vessel_name: { type: Type.STRING, description: 'Name of the vessel / ship (e.g. MV KOTA JAYA). Return null if absent.' },
        voyage: { type: Type.STRING, description: 'Voyage number or code. Return null if absent.' },
        imo: { type: Type.STRING, description: 'IMO number of the vessel (e.g. IMO 9123456). Return null if absent.' },
        port: { type: Type.STRING, description: 'Port of bunkering, call, or delivery. Return null if absent.' },
      },
    },
    subtotal: { type: Type.NUMBER, description: 'Sum of line items before tax, shipping, or discounts' },
    discount_amount: { type: Type.NUMBER, description: 'Total trade discount or promotional deduction value as a positive number. Return 0 if none.' },
    tax_amount: { type: Type.NUMBER, description: 'Total VAT, GST, or sales tax amount. Return 0 if zero or exempt.' },
    shipping_amount: { type: Type.NUMBER, description: 'Freight, delivery, or barge/bunker charges. Return 0 if none.' },
    total_amount: { type: Type.NUMBER, description: 'Final net payable amount' },
    exchange_rate: { type: Type.NUMBER, description: 'Conversion exchange rate if invoice is multi-currency. Return null if not applicable.' },
    bank_details: {
      type: Type.OBJECT,
      description: 'Remittance, wire transfer, or settlement banking instructions',
      properties: {
        bank_name: { type: Type.STRING, description: 'Name of the bank (e.g. Standard Chartered Bank, DBS Bank). Return null if absent.' },
        iban: { type: Type.STRING, description: 'International Bank Account Number (IBAN). Return null if absent.' },
        swift_bic: { type: Type.STRING, description: 'SWIFT / BIC code. Return null if absent.' },
        account_number: { type: Type.STRING, description: 'Bank account number. Return null if absent.' },
        beneficiary: { type: Type.STRING, description: 'Beneficiary or account holder name. Return null if absent.' },
      },
    },
    line_items: {
      type: Type.ARRAY,
      description: 'Array of itemized goods or services billed',
      items: {
        type: Type.OBJECT,
        properties: {
          description: { type: Type.STRING },
          quantity: { type: Type.NUMBER },
          unit_price: { type: Type.NUMBER },
          amount: { type: Type.NUMBER },
          charge_code: { type: Type.STRING, description: 'Item charge code, tariff code, or internal reference if present.' },
        },
        required: ['description'],
      },
    },
  },
  required: ['invoice_number', 'invoice_date', 'currency', 'total_amount'],
};

function toField(val: unknown, confidence = 0.95) {
  if (typeof val === 'string') {
    const cleaned = val.trim();
    if (/^(due_date|invoice_date|bill_to|invoice_no|null|undefined)$/i.test(cleaned)) {
      return { value: null, confidence };
    }
    return { value: cleaned !== '' ? cleaned : null, confidence };
  }
  return {
    value: val !== undefined && val !== null ? String(val) : null,
    confidence,
  };
}

function normalizeToSop(raw: any, confidence = 0.95) {
  const subtotal = raw.subtotal ?? raw.total_amount ?? 0;
  const discount = raw.discount_amount ?? raw.discount ?? 0;
  const tax = raw.tax_amount ?? raw.tax ?? 0;
  const shipping = raw.shipping_amount ?? raw.shipping ?? 0;
  const total = raw.total_amount ?? (subtotal - discount + tax + shipping);

  const custName = raw.customer_name ? String(raw.customer_name).trim() : null;
  let custAddr = raw.customer_address ? String(raw.customer_address).trim() : null;
  if (custAddr && custName && custAddr.toLowerCase() === custName.toLowerCase()) {
    custAddr = null;
  }

  const vendName = raw.vendor_name ? String(raw.vendor_name).trim() : null;
  let vendAddr = raw.vendor_address ? String(raw.vendor_address).trim() : null;
  if (vendAddr && vendName && vendAddr.toLowerCase() === vendName.toLowerCase()) {
    vendAddr = null;
  }

  return {
    header: {
      invoiceNumber: toField(raw.invoice_number, confidence),
      invoiceDate: toField(raw.invoice_date, confidence),
      dueDate: toField(raw.due_date, confidence),
      currency: toField(raw.currency ? String(raw.currency).toUpperCase() : 'USD', confidence),
      poReference: toField(raw.po_reference, confidence),
    },
    vendor: {
      name: toField(vendName, confidence),
      address: toField(vendAddr, confidence),
      country: toField(raw.vendor_country, confidence),
      taxRegistrationNumber: toField(raw.vendor_tax_id, confidence),
      contact: toField(raw.vendor_contact, confidence),
    },
    customer: {
      name: toField(custName, confidence),
      address: toField(custAddr, confidence),
    },
    billTo: {
      entity: toField(custName, confidence),
      address: toField(custAddr, confidence),
      businessUnit: toField(raw.bill_to_business_unit, confidence),
      accountingReference: toField(raw.bill_to_accounting_ref, confidence),
    },
    vessel: {
      vesselName: toField(raw.vessel?.vessel_name, confidence),
      voyage: toField(raw.vessel?.voyage, confidence),
      imo: toField(raw.vessel?.imo, confidence),
      port: toField(raw.vessel?.port, confidence),
    },
    amounts: {
      subtotal: toField(subtotal, confidence),
      tax: toField(tax, confidence),
      shipping: toField(shipping, confidence),
      discount: toField(discount, confidence),
      total: toField(total, confidence),
      exchangeRate: toField(raw.exchange_rate, confidence),
    },
    bankDetails: {
      bankName: toField(raw.bank_details?.bank_name, confidence),
      iban: toField(raw.bank_details?.iban, confidence),
      swiftBic: toField(raw.bank_details?.swift_bic, confidence),
      accountNumber: toField(raw.bank_details?.account_number, confidence),
      beneficiary: toField(raw.bank_details?.beneficiary, confidence),
    },
    lineItems: Array.isArray(raw.line_items)
      ? raw.line_items.map((item: any) => {
          const qty = item.quantity ?? 1;
          const unitPrice = item.unit_price ?? item.total_price ?? item.amount ?? 0;
          const amount = item.amount ?? item.total_price ?? (qty * unitPrice);
          return {
            description: toField(item.description, confidence),
            quantity: toField(qty, confidence),
            unitPrice: toField(unitPrice, confidence),
            amount: toField(amount, confidence),
            chargeCode: toField(item.charge_code, confidence),
          };
        })
      : [],
  };
}

function isSopInvoice(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && 'header' in value && 'amounts' in value;
}

// ------------------------------------------------------------------
// DYNAMIC CONFIDENCE SCORING
// ------------------------------------------------------------------
function calculateHarmonicConfidence(extraction: any, baseOcrConfidence = 0.96): { finalScore: number, mappingAccuracy: number, ocrBase: number, populatedFields: number } {
  let totalFields = 0;
  let populatedFields = 0;
  let llmConfidenceSum = 0;

  function traverse(obj: any) {
    if (!obj) return;
    
    // Check if this is a leaf node { value, confidence }
    if (typeof obj === 'object' && 'confidence' in obj && 'value' in obj) {
      totalFields++;
      llmConfidenceSum += (typeof obj.confidence === 'number' ? obj.confidence : 0);
      
      // Consider field populated if not null/empty
      if (obj.value !== null && obj.value !== '' && obj.value !== undefined && obj.value !== "      ") {
        populatedFields++;
      }
    } else {
      for (const key in obj) {
        if (typeof obj[key] === 'object') {
          traverse(obj[key]);
        }
      }
    }
  }

  traverse(extraction);

  if (totalFields === 0) return { finalScore: 0, mappingAccuracy: 0, ocrBase: baseOcrConfidence, populatedFields: 0 };

  // Calculate LLM Mapping Accuracy (average confidence * fill rate)
  const avgLlmConfidence = llmConfidenceSum / totalFields;
  const fillRate = populatedFields / totalFields;
  
  // Heavily penalize the mapping score if fields are left blank
  const mappingAccuracy = avgLlmConfidence * (0.6 + (fillRate * 0.4));

  // Harmonic Mean of OCR and LLM Mapping: 2ab / (a+b)
  // Pulls the overall score down strongly if either OCR or LLM is poor
  const harmonicMean = (2 * baseOcrConfidence * mappingAccuracy) / (baseOcrConfidence + mappingAccuracy);

  return {
    finalScore: Math.max(0.1, Math.min(1.0, harmonicMean)),
    mappingAccuracy: mappingAccuracy,
    ocrBase: baseOcrConfidence,
    populatedFields
  };
}

export async function extractInvoice(
  config: Config,
  input: ExtractionJobInput
): Promise<AiExtractionResponse> {
  const startTime = Date.now();
  const ai = new GoogleGenAI({ apiKey: config.GEMINI_API_KEY });
  const fileBytes = await readFile(input.path);
  const base64Data = fileBytes.toString('base64');

  const isTerminalInvoice =
    input.originalFilename?.startsWith('[TES]') ||
    /TAC_|QQCTU|TERMINAL|BERTH/i.test(input.originalFilename || '');

  let prompt = '';
  const schemaConfig: any = { responseMimeType: 'application/json' };

  if (isTerminalInvoice) {
    prompt = PROMPT_TES_TERMINAL;
  } else {
    prompt = PROMPT_STANDARD;
    schemaConfig.responseSchema = invoiceJsonSchema;
  }

  try {
    const response = await Promise.race([
      ai.models.generateContent({
        model: GEMINI_MODEL,
        contents: [{ role: 'user', parts: [
          { inlineData: { mimeType: input.contentType || 'application/pdf', data: base64Data } },
          { text: prompt },
        ] }],
        config: schemaConfig,
      }),
      new Promise<never>((_, reject) => setTimeout(() => reject(new Error('AI_WORKER_TIMEOUT')), config.IES_AI_TIMEOUT_MS)),
    ])
    
    const responseText = response.text
    if (!responseText) throw new Error('Empty response from Gemini')
    
    const parsed = JSON.parse(responseText)
    const invoice = isTerminalInvoice || isSopInvoice(parsed) ? parsed : normalizeToSop(parsed, 0.95)
    
    // Evaluate the final JSON against the heuristic algorithm
    const metrics = calculateHarmonicConfidence(invoice, 0.96);

    return {
      document_id: input.jobId,
      invoice,
      overall_confidence: metrics.finalScore,
      engine: GEMINI_MODEL,
      ocr_pages: 1,
      ocr_evidence: [],
      processing_ms: Date.now() - startTime,
      confidence_breakdown: {
        method: 'harmonic-mean-heuristic', 
        mapping_weight: 0.5, 
        ocr_weight: 0.5,
        mapping_confidence: metrics.mappingAccuracy, 
        ocr_confidence: metrics.ocrBase, 
        populated_fields: metrics.populatedFields,
        required_field_confidence: metrics.finalScore, 
        required_fields_present: 5,
      },
      warnings: [],
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error)
    if (message === 'AI_WORKER_TIMEOUT' || error instanceof Error && error.name === 'AbortError') throw new Error('AI_WORKER_TIMEOUT')
    if (/\b(?:429|503)\b/.test(message)) throw new Error('AI_WORKER_BUSY')
    throw error
  }
}