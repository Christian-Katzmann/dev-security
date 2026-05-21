import { motion } from 'motion/react';
import { Cpu, TerminalSquare, AlertTriangle } from 'lucide-react';
import {DashboardSummary, formatLocation, scannerCount, sortedFindings} from '../dashboardData';

type McpViewProps = {
  summary: DashboardSummary;
};

export default function McpView({summary}: McpViewProps) {
  const aiFindings = sortedFindings(summary, 'ai-risk');
  const topFinding = aiFindings[0];
  const toolSignals = scannerCount(summary, 'medusa') || aiFindings.length;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className="relative flex flex-col w-full p-6 md:p-12 max-w-[1400px] mx-auto gap-8"
    >
      <div className="flex justify-between items-end border-b border-black/10 pb-6 shrink-0 relative z-10">
        <div>
          <h2 className="text-3xl font-light text-black tracking-tight">Agent Posture & MCP</h2>
          <p className="font-mono text-xs text-black/50 uppercase tracking-widest mt-2 inline-block px-2 py-1 bg-white/40">
            LLM Input/Output Vectors
          </p>
        </div>
      </div>

      <div className="w-full h-[500px] shrink-0 relative border border-black/10 bg-white/50 overflow-hidden shadow-sm">
        
        {/* Massive Whale-inspired stippled shape (Image 1) representing the LLM/Agent */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
           <svg viewBox="0 0 1000 600" preserveAspectRatio="none" className="w-full h-full opacity-60">
              <defs>
                 <pattern id="stipplePattern" width="4" height="4" patternUnits="userSpaceOnUse">
                    <circle cx="2" cy="2" r="0.8" fill="#111" opacity="0.3"/>
                 </pattern>
                 <pattern id="stipplePatternDense" width="3" height="3" patternUnits="userSpaceOnUse">
                    <circle cx="1.5" cy="1.5" r="1" fill="#111" opacity="0.5"/>
                 </pattern>
                 {/* Gradient mask to make it fade nicely */}
                 <linearGradient id="whaleMask" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="white" stopOpacity="1" />
                    <stop offset="100%" stopColor="white" stopOpacity="0" />
                 </linearGradient>
              </defs>
              <g mask="url(#whaleMask)">
                 <path d="M-200,600 C 200,600 300,100 800,200 C 1200,250 1100,600 1200,600 Z" fill="url(#stipplePattern)" />
                 <path d="M-200,600 C 250,550 400,200 800,250 C 1100,300 1000,600 1200,600 Z" fill="url(#stipplePatternDense)" />
              </g>
           </svg>
        </div>

        <div className="absolute inset-x-8 inset-y-8 flex gap-8 z-10 max-w-full">
           
           {/* "The Minnow" - small deterministic app config */}
           <div className="w-72 md:w-80 flex flex-col gap-4">
              <div className="bg-white/90 backdrop-blur-sm border border-black p-6 shadow-sm">
                 <div className="flex items-center gap-3 mb-4">
                    <TerminalSquare className="w-4 h-4 text-black" />
                    <h3 className="font-mono text-xs uppercase tracking-widest text-black/60">Host Application</h3>
                 </div>
                 <h4 className="text-xl font-medium mb-2">MCP Router</h4>
                 <div className="font-mono text-[10px] text-black/50 border-t border-black/10 pt-4 mt-4">
                    Signals: {toolSignals}<br/>
                    Boundary: {aiFindings.length ? 'Weak' : 'Stable'}
                 </div>
              </div>

              {/* Threat arrow */}
              <div className="flex-1 flex items-center justify-center relative opacity-40">
                 <div className="absolute w-[2px] h-full bg-black left-1/2 -ml-[1px]" />
                 <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="black" strokeWidth="2" className="absolute top-1/2 -mt-3 bg-[#f9f9f9] py-1">
                    <path d="M12 5v14M19 12l-7 7-7-7" />
                 </svg>
              </div>

              <div className="bg-white/90 backdrop-blur-sm border border-graph-gold p-6 shadow-[0_4px_20px_rgba(212,166,45,0.15)] relative overflow-hidden">
                 <div className="absolute top-0 right-0 bg-graph-gold text-white font-mono text-[8px] px-2 py-0.5 uppercase">Threat</div>
                 <div className="flex items-center gap-3 mb-4">
                    <AlertTriangle className="w-4 h-4 text-graph-gold" />
                    <h3 className="font-mono text-xs uppercase tracking-widest text-graph-gold">Jailbreak Payload</h3>
                 </div>
                 <h4 className="text-sm border-b border-graph-gold/20 pb-2 mb-2">{topFinding?.title ?? 'Indirect Prompt Injection'}</h4>
                 <p className="font-mono text-[10px] text-black/60 leading-tight">
                    Payload originating from <span className="text-black bg-black/5 px-1">{topFinding ? formatLocation(topFinding) : 'local scan'}</span> {topFinding ? topFinding.severity : 'ready'}.
                 </p>
              </div>
           </div>

           {/* "The Whale" Data Box */}
           <div className="flex-1 flex justify-end">
              <div className="w-96 bg-[#111]/95 text-white p-8 border border-white/10 self-start shadow-xl relative overflow-hidden">
                 <div className="absolute top-0 right-0 p-4 opacity-10">
                    <Cpu className="w-32 h-32" strokeWidth={0.5} />
                 </div>
                 <h3 className="font-mono text-[10px] uppercase tracking-widest text-white/40 mb-6">Foundational Model Intercept</h3>
                 <div className="space-y-6 relative z-10">
                    <div>
                       <div className="font-mono text-[10px] text-white/40 mb-1">Target Model</div>
                       <div className="text-lg">{topFinding?.repo_name ?? 'local-agent-surface'}</div>
                    </div>
                    <div>
                       <div className="font-mono text-[10px] text-white/40 mb-1">Raw Token Delta</div>
                       <div className="text-lg">{summary.repos.length} ➔ <span className="text-graph-gold animate-pulse">{aiFindings.length}</span></div>
                       <div className="font-mono text-[9px] text-graph-gold mt-1">Agentic risk signals detected in local scans</div>
                    </div>
                    <div className="border border-white/20 p-4 bg-black">
                       <div className="font-mono text-[9px] text-white/40 mb-2 uppercase border-b border-white/20 pb-1">Extracted Prompt Tail</div>
                       <p className="font-mono text-[10px] text-white/70 italic">
                          " ...{topFinding?.remediation ?? topFinding?.title ?? 'run the AI scanner profile to inspect prompt and tool boundaries'}... "
                       </p>
                    </div>
                 </div>
              </div>
           </div>

        </div>

      </div>

      <div className="grid grid-cols-12 gap-8 mt-4 pb-12 shrink-0">
          <div className="col-span-12 md:col-span-4 bg-white/50 border border-black/5 p-6 flex flex-col gap-4">
             <h3 className="font-mono text-[10px] tracking-widest text-black/40 uppercase mb-2 border-b border-black/5 pb-2">Active Context Tools</h3>
             <ul className="space-y-3 font-mono text-xs">
                <li className="flex justify-between items-center bg-[#fbfbfb] border border-black/5 p-2">
                   <div className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 bg-black rounded-full" />
                      semgrep
                   </div>
                   <span className="text-black/40">{scannerCount(summary, 'semgrep')}</span>
                </li>
                <li className="flex justify-between items-center bg-[#fbfbfb] border border-black/5 p-2">
                   <div className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 bg-graph-gold rounded-full animate-pulse" />
                      medusa
                   </div>
                   <span className="text-graph-gold font-medium">{scannerCount(summary, 'medusa')}</span>
                </li>
                <li className="flex justify-between items-center bg-[#fbfbfb] border border-black/5 p-2">
                   <div className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 bg-black rounded-full" />
                      local-static
                   </div>
                   <span className="text-black/40">{aiFindings.length}</span>
                </li>
             </ul>
          </div>

          <div className="col-span-12 md:col-span-8 bg-[#111] border border-white/10 p-6 flex flex-col gap-4 text-white">
             <h3 className="font-mono text-[10px] tracking-widest text-white/40 uppercase mb-2 border-b border-white/10 pb-2">RPC Call Intercept Log</h3>
             <div className="space-y-2 overflow-auto max-h-[160px] pr-2">
                {(aiFindings.length ? aiFindings.slice(0, 6).map((finding) => ({
                  time: new Date(finding.created_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}),
                  source: finding.repo_name,
                  action: finding.scanner,
                  target: formatLocation(finding),
                  status: finding.severity,
                  color: finding.severity === 'critical' || finding.severity === 'high' ? 'text-graph-gold' : 'text-white/60',
                })) : [{
                  time: '--:--',
                  source: 'dashboard',
                  action: 'waiting',
                  target: 'security-scan --ai',
                  status: 'Ready',
                  color: 'text-white/60',
                }]).map((log, i) => (
                   <div key={i} className="flex items-center justify-between font-mono text-[10px] border-b border-white/5 pb-2">
                      <div className="flex gap-4">
                         <span className="text-white/30">{log.time}</span>
                         <span className="text-white/50">{log.source}</span>
                         <span>{log.action}</span>
                         <span className="text-white/80">{log.target}</span>
                      </div>
                      <span className={"uppercase tracking-widest " + log.color}>{log.status}</span>
                   </div>
                ))}
             </div>
          </div>
      </div>
    </motion.div>
  );
}
