import { motion } from 'motion/react';
import { AlertCircle, FileCode, Search } from 'lucide-react';
import {useMemo, useState} from 'react';
import {DashboardSummary, Finding, formatLocation, sortedFindings} from '../dashboardData';

const lineWeights = [1.1, 1.8, 1.4, 2.2, 1.3, 1.9, 1.5, 2.1, 1.2, 1.7];
const lineOpacities = [0.06, 0.12, 0.09, 0.18, 0.08, 0.14, 0.11, 0.16, 0.07, 0.13];

type CodeViewProps = {
  summary: DashboardSummary;
};

function fallbackFinding(): Finding {
  return {
    id: 0,
    scan_id: 'empty',
    repo_name: 'local',
    scanner: 'dashboard',
    severity: 'info',
    category: 'code-security',
    title: 'No code findings recorded',
    file: 'Run security-scan --quick',
    line: null,
    remediation: 'Code-level findings will appear here after a scan.',
    fingerprint: 'empty-code',
    created_at: new Date().toISOString(),
  };
}

export default function CodeView({summary}: CodeViewProps) {
  const [query, setQuery] = useState('');
  const findings = useMemo(() => {
    const candidates = sortedFindings(summary).filter((finding) =>
      ['code-security', 'secrets', 'ai-risk'].includes(finding.category),
    );
    const filtered = candidates.filter((finding) => {
      const haystack = `${finding.title} ${finding.file ?? ''} ${finding.repo_name}`.toLowerCase();
      return haystack.includes(query.toLowerCase());
    });
    return filtered.length ? filtered : [fallbackFinding()];
  }, [query, summary]);
  const selected = findings[0];
  const lines = Array.from({ length: 25 }, (_, i) => {
    const yOffset = i * 16;
    return (
      <path
        key={i}
        d={`M-100,${100 + yOffset} C300,${300 + yOffset} 600,${50 + yOffset} 1200,${250 + yOffset}`}
        stroke="currentColor"
        strokeWidth={lineWeights[i % lineWeights.length]}
        fill="none"
        style={{ opacity: lineOpacities[i % lineOpacities.length] }}
      />
    );
  });

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className="relative flex flex-col w-full p-6 md:p-12 max-w-[1400px] mx-auto min-h-full gap-8"
    >
      {/* Flowing Contours Background (Image 2 - Cat inspiration) */}
      <svg className="absolute inset-0 w-[120%] min-h-full h-[150vh] pointer-events-none text-black mix-blend-multiply" preserveAspectRatio="none" viewBox="0 0 1000 500">
        <motion.g 
          initial={{ x: -50, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 1.5, ease: "easeOut" }}
        >
          {lines}
        </motion.g>
      </svg>

      <div className="relative z-10 flex flex-col w-full mx-auto self-stretch gap-8">
        <div className="flex flex-col md:flex-row gap-6 justify-between items-start md:items-end border-b border-black/10 pb-6 mb-2 shrink-0">
          <div>
            <h2 className="text-3xl font-light text-black tracking-tight">Data Flow & Integrity</h2>
            <p className="font-mono text-xs text-black/50 uppercase tracking-widest mt-2 bg-white/40 inline-block px-2 py-1">
              Static Code Analysis
            </p>
          </div>
          <div className="relative w-full md:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-black/40" />
            <input 
              type="text" 
              placeholder="Filter vectors..." 
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full bg-white/50 border border-black/10 px-10 py-2 text-xs font-mono placeholder:text-black/30 text-black focus:outline-none focus:border-black/50 transition-colors"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 flex-1">
          {/* Main List representing the splintering fragmentation (Image 6 - Splintered Head) */}
          <div className="md:col-span-8 flex flex-col gap-4">
            {findings.slice(0, 3).map((issue, idx) => (
              <motion.div 
                key={issue.fingerprint}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 * idx }}
                className="group relative flex border border-black min-h-[140px] bg-[#111] hover:bg-black transition-colors"
              >
                <div className="flex flex-col justify-between p-6 w-full pr-32 z-10 relative">
                  <div className="flex items-center gap-4 mb-2">
                    <AlertCircle className="w-4 h-4 text-graph-gold" />
                    <span className="font-mono text-[10px] text-white/50 uppercase tracking-widest">{formatLocation(issue)}</span>
                    <span className={"font-mono text-[10px] border px-2 " + (issue.severity === 'critical' ? 'border-graph-gold text-graph-gold' : 'border-white/20 text-white/50')}>
                      {issue.severity}
                    </span>
                  </div>
                  <h3 className="text-xl font-medium text-white">{issue.title}</h3>
                </div>
                
                {/* Visual Splintering Effect on the right edge */}
                <div className="absolute right-0 top-0 bottom-0 w-64 overflow-hidden pointer-events-none flex">
                  {/* The solid part fading out */}
                  <div className="w-full h-full bg-gradient-to-r from-[#111] to-transparent z-0" />
                  
                  {/* Generated floating particle blocks */}
                  <div className="absolute inset-0 flex flex-wrap content-center justify-end gap-1 p-2">
                    {Array.from({ length: issue.severity === 'critical' ? 20 : issue.severity === 'high' ? 15 : 8 }).map((_, i) => (
                      <motion.div 
                        key={i}
                        initial={{ opacity: 0, scale: 0 }}
                        animate={{ opacity: 0.25 + ((i % 5) * 0.14), scale: 0.7 + ((i % 4) * 0.25) }}
                        transition={{ delay: 0.2 + ((i % 6) * 0.07), duration: 2, repeat: Infinity, repeatType: "mirror" }}
                        className="bg-white/20"
                        style={{
                          width: `${2 + (i % 6)}px`,
                          height: `${2 + ((i * 2) % 6)}px`,
                          transform: `translate(${(i % 7) * 3}px, ${((i % 9) - 4) * 5}px)`
                        }}
                      />
                    ))}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Context Sidebar */}
          <div className="md:col-span-4 flex flex-col gap-6">
            <div className="border border-black/10 bg-white/40 backdrop-blur-md p-6 h-full flex flex-col">
              <h4 className="font-mono text-[10px] uppercase text-black/40 tracking-widest mb-6 flex items-center gap-2">
                <FileCode className="w-3 h-3" /> Selected Trace
              </h4>
              
              <div className="flex-1 border-l box-border border-black/20 pl-6 flex flex-col gap-6 relative">
                 {/* Timeline dots */}
                 <div className="absolute left-[-4px] top-0 bottom-0 flex flex-col gap-[3rem]">
                    <div className="w-2 h-2 bg-black rounded-full" />
                    <div className="w-2 h-2 border border-black bg-white rounded-full" />
                    <div className="w-2 h-2 bg-graph-gold rounded-full shadow-[0_0_8px_rgba(212,166,45,0.5)]" />
                 </div>

                 <div>
                   <p className="font-mono text-[10px] text-black/40 mb-1">Source / Input</p>
                   <p className="text-sm font-medium">{selected.repo_name}</p>
                 </div>
                 
                 <div>
                   <p className="font-mono text-[10px] text-black/40 mb-1">Transformation</p>
                   <p className="text-sm">{selected.scanner}</p>
                 </div>

                 <div>
                   <p className="font-mono text-[10px] text-graph-gold mb-1 uppercase">Sink / Execration</p>
                   <p className="text-sm font-medium text-black">{selected.category}</p>
                   <div className="mt-4 bg-black/5 p-3 font-mono text-[10px] text-black border border-black/10">
                     {formatLocation(selected)}: {selected.remediation ?? selected.title}
                   </div>
                 </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
