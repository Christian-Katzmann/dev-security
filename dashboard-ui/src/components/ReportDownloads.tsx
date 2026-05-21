import {Download, FileJson, FileText} from 'lucide-react';
import {reportViewUrl} from '../dashboardData';

type ReportDownloadsProps = {
  scanId: string;
  compact?: boolean;
};

export default function ReportDownloads({scanId, compact = false}: ReportDownloadsProps) {
  const buttonClass = compact
    ? 'inline-flex items-center gap-1.5 border border-black/10 bg-white/40 px-2 py-1 font-mono text-[9px] uppercase tracking-widest text-black/45 hover:text-black hover:border-black/30 transition-colors'
    : 'inline-flex items-center justify-center gap-2 border border-black/10 bg-white/55 px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-black/55 hover:text-black hover:border-black/30 transition-colors';

  return (
    <div className={`flex flex-wrap gap-2 ${compact ? 'justify-start lg:justify-end' : ''}`}>
      <a href={reportViewUrl(scanId, 'raw')} className={buttonClass}>
        {compact ? <FileJson className="w-3 h-3" strokeWidth={1.5} /> : <Download className="w-3.5 h-3.5" strokeWidth={1.5} />}
        Full report
      </a>
      <a href={reportViewUrl(scanId, 'prompt')} className={buttonClass}>
        <FileText className={compact ? 'w-3 h-3' : 'w-3.5 h-3.5'} strokeWidth={1.5} />
        AI prompt
      </a>
    </div>
  );
}
