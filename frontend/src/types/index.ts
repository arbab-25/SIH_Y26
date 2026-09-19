export type Verdict = 'COMPLIANT' | 'NON_COMPLIANT' | 'NEEDS_REVIEW';

export interface User {
  id: string;
  name: string;
  email?: string;
  mobile?: string;
  role: 'INSPECTOR' | 'SENIOR_OFFICER' | 'ADMIN';
  designation?: string;
  office?: string;
  district?: string;
  state?: string;
}

export interface ExtractedFieldItem {
  id?: string;
  field_key: string;
  field_value: string;
  confidence: number;
  bbox?: number[][];
  status: Verdict;
}

export interface ViolationItem {
  id?: string;
  field_key: string;
  rule_ref: string;
  severity: 'MAJOR' | 'MINOR';
  message_en: string;
  message_hi?: string;
  suggested_fix?: string;
}

export interface PieSlice {
  name: string;
  value: number;
  fields?: string[];
  color: string;
}

export interface ScanResult {
  id: string;
  scan_id: string;
  status: 'queued' | 'processing' | 'done' | 'failed';
  verdict: Verdict;
  compliance_score: number;
  avg_ocr_confidence: number;
  processing_time_ms: number;
  category?: string;
  package_type?: string;
  created_at: string;
  product?: {
    name: string;
    brand?: string;
    manufacturer_name?: string;
    manufacturer_address?: string;
    pin_code?: string;
    net_quantity?: string;
    mrp?: string;
    fssai_number?: string;
    consumer_care_phone?: string;
    consumer_care_email?: string;
    barcode_gtin?: string;
  };
  extracted_fields: ExtractedFieldItem[];
  violations: ViolationItem[];
  confidence_pie: PieSlice[];
  disclaimer: string;
}

export interface RuleItem {
  id: string;
  rule_number: string;
  chapter: string;
  title: string;
  full_text: string;
  schedule_ref?: string;
  applies_to?: string[];
  source_page?: number;
  highlight?: string;
}

export interface ReportItem {
  id: string;
  report_number: string;
  created_at: string;
  pdf_url: string;
  verdict: Verdict;
  compliance_score: number;
  product_name: string;
  manufacturer_name: string;
  category: string;
  inspector_name?: string;
}

export interface DashboardStats {
  scans_today: number;
  scans_this_week: number;
  scans_this_month: number;
  total_scans: number;
  average_ocr_confidence: number;
  verdict_breakdown: {
    compliant: number;
    non_compliant: number;
    needs_review: number;
  };
  top_violated_rules: {
    rule: string;
    field: string;
    violations_count: number;
  }[];
  top_non_compliant_manufacturers: {
    manufacturer: string;
    violations_count: number;
  }[];
  compliance_trend: {
    date: string;
    compliant: number;
    non_compliant: number;
    needs_review: number;
  }[];
}
