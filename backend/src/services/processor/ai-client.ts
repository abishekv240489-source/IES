import { readFile } from 'node:fs/promises'
import { z } from 'zod'
import { GoogleGenAI, Type } from '@google/genai'
import type { Config } from '../../config.js'
import type { AiExtractionResponse } from '../../domain/types.js'

const responseSchema = z.object({
  document_id: z.string(),
  invoice: z.record(z.string(), z.unknown()),
  overall_confidence: z.number().min(0).max(1),
  engine: z.string().min(1),
  ocr_pages: z.number().int().nonnegative(),
  ocr_evidence: z.array(z.object({
    page: z.number().int().positive(),
    text: z.string(),
    confidence: z.number().min(0).max(1),
    quality_score: z.number().min(0).max(1),
    used_preprocessing: z.boolean(),
  })),
  processing_ms: z.number().nonnegative(),
  confidence_breakdown: z.object({
    method: z.string().min(1),
    mapping_weight: z.number().min(0).max(1),
    ocr_weight: z.number().min(0).max(1),
    mapping_confidence: z.number().min(0).max(1),
    ocr_confidence: z.number().min(0).max(1),
    populated_fields: z.number().int().nonnegative(),
    required_field_confidence: z.number().min(0).max(1),
    required_fields_present: z.number().int().min(0).max(5),
  }),
  warnings: z.array(z.string()),
})

function scalar(desc: string) {
  return {
    type: Type.OBJECT,
    description: desc,
    properties: {
      value: { type: Type.STRING },
      confidence: { type: Type.NUMBER }
    },
    required: ['value', 'confidence']
  }
}

const invoiceSchema = {
  type: Type.OBJECT,
  properties: {
    header: {
      type: Type.OBJECT,
      properties: {
        invoiceNumber: scalar('Invoice number'),
        invoiceDate: scalar('Invoice date (YYYY-MM-DD)'),
        dueDate: scalar('Due date (YYYY-MM-DD)'),
        currency: scalar('Currency code (3 letters)'),
        poReference: scalar('Purchase order reference'),
      },
      required: ['invoiceNumber', 'invoiceDate', 'currency']
    },
    vendor: {
      type: Type.OBJECT,
      properties: {
        vendorName: scalar('Vendor name'),
        taxRegNumber: scalar('Tax registration number'),
        address: scalar('Vendor address'),
        country: scalar('Vendor country'),
      },
      required: ['vendorName']
    },
    billTo: {
      type: Type.OBJECT,
      properties: {
        billToEntity: scalar('Bill to entity name'),
        address: scalar('Bill to address'),
        businessUnit: scalar('Business unit'),
      },
      required: []
    },
    vessel: {
      type: Type.OBJECT,
      properties: {
        vesselName: scalar('Vessel name'),
        voyage: scalar('Voyage number'),
        imo: scalar('IMO number'),
        port: scalar('Port'),
      },
      required: []
    },
    amounts: {
      type: Type.OBJECT,
      properties: {
        subtotal: scalar('Subtotal amount'),
        tax: scalar('Tax amount'),
        total: scalar('Total amount'),
        currencyCode: scalar('Currency code for amounts'),
      },
      required: ['total']
    },
    bankDetails: {
      type: Type.OBJECT,
      properties: {
        bankName: scalar('Bank name'),
        iban: scalar('IBAN'),
        swift: scalar('SWIFT code'),
        accountNumber: scalar('Bank account number'),
      },
      required: []
    },
    lineItems: {
      type: Type.ARRAY,
      items: {
        type: Type.OBJECT,
        properties: {
          description: scalar('Line item description'),
          quantity: scalar('Quantity'),
          unitPrice: scalar('Unit price'),
          lineAmount: scalar('Line amount'),
          chargeCode: scalar('Charge code'),
        },
        required: ['description']
      }
    }
  },
  required: ['header', 'vendor', 'amounts', 'lineItems']
}

export async function extractInvoice(
  config: Config,
  input: { jobId: string; path: string; originalFilename: string; contentType: string },
): Promise<AiExtractionResponse> {
  const bytes = await readFile(input.path)
  const base64Data = bytes.toString('base64')

  const ai = new GoogleGenAI({ apiKey: config.GEMINI_API_KEY })

  const timeout = AbortSignal.timeout(config.IES_AI_TIMEOUT_MS)

  const startTime = Date.now()

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-1.5-flash',
      contents: [
        {
          role: 'user',
          parts: [
            {
              inlineData: {
                mimeType: input.contentType || 'application/pdf',
                data: base64Data,
              }
            },
            {
              text: 'Extract invoice details from this document according to the schema.'
            }
          ]
        }
      ],
      config: {
        responseMimeType: 'application/json',
        responseSchema: invoiceSchema,
      }
    })

    if (timeout.aborted) {
      throw new Error('AI_WORKER_TIMEOUT')
    }

    const responseText = response.text
    if (!responseText) {
      throw new Error('Empty response from AI')
    }

    const invoiceData = JSON.parse(responseText)

    const processing_ms = Date.now() - startTime

    const aiResponse: AiExtractionResponse = {
      document_id: input.jobId,
      invoice: invoiceData,
      overall_confidence: 0.9,
      engine: 'gemini-1.5-flash',
      ocr_pages: 1,
      ocr_evidence: [],
      processing_ms,
      confidence_breakdown: {
        method: 'gemini',
        mapping_weight: 1.0,
        ocr_weight: 0.0,
        mapping_confidence: 0.9,
        ocr_confidence: 1.0,
        populated_fields: Object.keys(invoiceData).length,
        required_field_confidence: 0.9,
        required_fields_present: 5,
      },
      warnings: [],
    }

    return responseSchema.parse(aiResponse)
  } catch (err: unknown) {
    if (timeout.aborted || (err instanceof Error && err.name === 'AbortError') || (err instanceof Error && err.message.includes('fetch failed') && timeout.aborted)) {
      throw new Error('AI_WORKER_TIMEOUT')
    }
    if (err instanceof Error && err.message.includes('503')) {
      throw new Error('AI_WORKER_BUSY')
    }
    throw err
  }
}
