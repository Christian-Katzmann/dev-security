import {DashboardSummary, ScannerDoctorItem, scannerDoctorGroups} from './dashboardData';
import {Tone} from './uiTypes';

export function humanizeKey(value: string): string {
  const acronyms: Record<string, string> = {
    ai: 'AI',
    api: 'API',
    cve: 'CVE',
    iac: 'IaC',
    ioc: 'IOC',
    mcp: 'MCP',
    osv: 'OSV',
    sbom: 'SBOM',
    scm: 'SCM',
    ssl: 'SSL',
    tls: 'TLS',
  };
  return value
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => acronyms[part.toLowerCase()] ?? `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

export function topScannerItems(summary: DashboardSummary): ScannerDoctorItem[] {
  return scannerDoctorGroups(summary).flatMap((group) => group.items);
}

export function scannerStatusTone(status: ScannerDoctorItem['status']): Tone {
  if (status === 'ran') return 'low';
  if (status === 'not-run') return 'info';
  if (status === 'missing') return 'warn';
  return 'crit';
}

export function safetyLabelTone(label: string): Tone {
  const normalized = label.toLowerCase();
  if (normalized.includes('sends source') || normalized.includes('destructive')) return 'crit';
  if (normalized.includes('network required') || normalized.includes('needs credentials') || normalized.includes('approval required') || normalized.includes('writes files')) return 'warn';
  if (normalized.includes('optional network') || normalized.includes('blocked')) return 'info';
  return normalized.includes('display only') ? 'neutral' : 'low';
}

export async function responseErrorMessage(response: Response, fallback: string): Promise<string> {
  const text = await response.text();
  const cleanText = text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  return cleanText || fallback;
}
