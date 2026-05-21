import { motion } from 'motion/react';
import { Cloud, GitBranch, KeyRound, Lock } from 'lucide-react';
import {DashboardSummary, formatLocation, platformPostureFindings, platformPostureSnapshots, sortedFindings} from '../dashboardData';

type IacViewProps = {
  summary: DashboardSummary;
};

export default function IacView({summary}: IacViewProps) {
  const iacFindings = sortedFindings(summary, 'iac');
  const workflowFindings = sortedFindings(summary, 'workflow');
  const platformFindings = platformPostureFindings(summary);
  const postureFindings = [...platformFindings, ...workflowFindings, ...iacFindings].sort((a, b) => severityRank(b.severity) - severityRank(a.severity));
  const platformSnapshots = platformPostureSnapshots(summary);
  const platformScannerSeen = summary.repos.some((repo) => repo.scanners.some((scanner) => scanner.scanner === 'legitify'));
  const platformChecked = platformSnapshots.some((snapshot) => snapshot.status === 'checked' || snapshot.status === 'partial');
  const platformAttempted = platformScannerSeen || platformSnapshots.length > 0;
  const platformStatus = platformChecked
    ? platformFindings.length ? `Issues (${platformFindings.length})` : 'Checked'
    : platformAttempted ? 'Skipped' : 'Not checked';
  const driftFinding = platformFindings.find((finding) => finding.scanner === 'legitify-drift');
  const tokenFinding = platformFindings.find((finding) => /token|workflow/i.test(finding.title));
  const first = postureFindings[0];
  const second = postureFindings[1];
  const third = postureFindings[2];

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className="relative flex flex-col w-full p-6 md:p-12 max-w-[1400px] mx-auto gap-8 bg-[#fbfbfb]"
    >
      <div className="flex justify-between items-end border-b border-black/5 pb-6 shrink-0 z-10">
        <div>
          <h2 className="text-3xl font-light text-black tracking-tight drop-shadow-sm">Infrastructure Posture</h2>
          <p className="font-mono text-xs text-black/40 uppercase tracking-widest mt-2 px-2 py-1 bg-white inline-block shadow-sm">
            IaC Configuration Analysis
          </p>
        </div>
      </div>

      <div className="w-full h-[600px] relative shrink-0 border border-black/5 bg-white/50 group overflow-hidden">
        {/* Connection circuit paths (Image 5 Cybernetic Head) via SVG spanning 100% */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-0" viewBox="0 0 1000 600" preserveAspectRatio="none">
           <path d="M 0,100 L 250,100 L 250,300 L 500,300" stroke="#d4a62d" strokeWidth="1" fill="none" className="drop-shadow-[0_0_4px_rgba(212,166,45,0.3)]"/>
           <path d="M 250,300 L 250,500 L 750,500 L 1000,500" stroke="rgba(0,0,0,0.1)" strokeWidth="1" fill="none"/>
           <path d="M 500,300 L 750,300 L 750,500" stroke="#d4a62d" strokeWidth="1" fill="none" className="drop-shadow-[0_0_4px_rgba(212,166,45,0.3)]"/>
           <circle cx="250" cy="100" r="3" fill="#fdfdfd" stroke="#d4a62d" strokeWidth="1.5" className="drop-shadow-sm" />
           <circle cx="500" cy="300" r="3" fill="#fdfdfd" stroke="#111" strokeWidth="1.5" className="drop-shadow-sm" />
           <circle cx="750" cy="500" r="3" fill="#fdfdfd" stroke="#d4a62d" strokeWidth="1.5" className="drop-shadow-sm" />
        </svg>

        {/* Nodes positioned via flex/grid over the SVG */}
        <div className="absolute inset-0 pointer-events-none">
           
           <div className="absolute top-[100px] left-[25%] -translate-x-[50%] -translate-y-1/2 z-10 w-64 embossed-plate p-6 pointer-events-auto hover:scale-105 transition-transform">
              <div className="flex justify-between items-start mb-4">
                 <Cloud className="w-5 h-5 text-black/50" />
                 <div className="flex gap-1">
                   <div className="w-2 h-2 embossed-rivet" />
                   <div className="w-2 h-2 embossed-rivet" />
                 </div>
              </div>
              <h3 className="text-sm font-medium mb-1 text-black">{first?.title ?? (platformChecked ? 'No platform posture finding' : 'Platform posture not checked')}</h3>
              <p className="font-mono text-[10px] text-black/40">{first ? formatLocation(first) : platformChecked ? 'Run security-scan --iac' : 'Run security-scan --platform-posture'}</p>
              <div className="mt-4 pt-4 border-t border-black/5 flex items-center justify-between">
                 <span className="font-mono text-[10px] uppercase text-graph-gold shadow-[0_0_8px_rgba(212,166,45,0.1)]">{first?.severity ?? 'Ready'}</span>
                 <div className="w-4 h-4 rounded-full bg-[#fdfdfd] shadow-[inset_1px_1px_2px_rgba(0,0,0,0.1)] flex items-center justify-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-graph-gold animate-pulse shadow-[0_0_8px_rgba(212,166,45,0.8)]" />
                 </div>
              </div>
           </div>

           <div className="absolute top-[300px] left-[50%] -translate-x-[50%] -translate-y-1/2 z-10 w-64 embossed-plate p-6 pointer-events-auto hover:scale-105 transition-transform">
              <div className="flex justify-between items-start mb-4">
                 <Lock className="w-5 h-5 text-black/50" />
                 <div className="flex gap-1">
                   <div className="w-2 h-2 embossed-rivet" />
                   <div className="w-2 h-2 embossed-rivet" />
                 </div>
              </div>
              <h3 className="text-sm font-medium mb-1 text-black">{second?.title ?? 'No infrastructure policy finding'}</h3>
              <p className="font-mono text-[10px] text-black/40">{second ? formatLocation(second) : iacFindings.length ? 'Infrastructure scanner idle' : 'Run security-scan --iac'}</p>
              <div className="mt-4 pt-4 border-t border-black/5 flex items-center justify-between">
                 <span className="font-mono text-[10px] uppercase text-black/60">{second?.severity ?? 'Passed'}</span>
                 <div className="w-4 h-4 rounded-full bg-[#fdfdfd] shadow-[inset_1px_1px_2px_rgba(0,0,0,0.1)] flex items-center justify-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-black/20" />
                 </div>
              </div>
           </div>

           <div className="absolute top-[500px] left-[75%] -translate-x-[50%] -translate-y-1/2 z-10 w-64 embossed-plate p-6 pointer-events-auto hover:scale-105 transition-transform">
              <div className="flex justify-between items-start mb-4">
                 <GitBranch className="w-5 h-5 text-black/50" />
                 <div className="flex gap-1">
                   <div className="w-2 h-2 embossed-rivet" />
                   <div className="w-2 h-2 embossed-rivet" />
                 </div>
              </div>
              <h3 className="text-sm font-medium mb-1 text-black">{third?.title ?? (platformChecked ? 'No platform drift finding' : 'SCM boundary unknown')}</h3>
              <p className="font-mono text-[10px] text-black/40">{third ? formatLocation(third) : platformChecked ? 'No posture drift saved' : 'Token-backed check absent'}</p>
              <div className="mt-4 pt-4 border-t border-black/5 flex items-center justify-between">
                 <span className="font-mono text-[10px] uppercase text-graph-gold shadow-[0_0_8px_rgba(212,166,45,0.1)]">{third?.severity ?? 'Ready'}</span>
                 <div className="w-4 h-4 rounded-full bg-[#fdfdfd] shadow-[inset_1px_1px_2px_rgba(0,0,0,0.1)] flex items-center justify-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-graph-gold animate-pulse shadow-[0_0_8px_rgba(212,166,45,0.8)]" />
                 </div>
              </div>
           </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-4 pb-12 shrink-0">
         <div className="bg-white border border-black/5 p-8 flex flex-col gap-6">
            <h3 className="font-mono text-[10px] tracking-widest uppercase text-black/40 border-b border-black/5 pb-2">Policy Execution Matrix</h3>
            <div className="flex flex-col gap-3 font-mono text-xs">
               <div className="flex justify-between p-2 bg-[#f9f9f9] border border-black/10">
                  <span className="text-black/60">Infrastructure rules</span>
                  <span className="text-graph-gold font-medium">{iacFindings.length ? `Violated (${iacFindings.length})` : 'No active findings'}</span>
               </div>
               <div className="flex justify-between p-2 bg-[#f9f9f9] border border-black/10">
                  <span className="text-black/60">Workflow surfaces</span>
                  <span className="text-black font-medium">{workflowFindings.length ? `Flagged (${workflowFindings.length})` : 'No active findings'}</span>
               </div>
               <div className="flex justify-between p-2 bg-[#f9f9f9] border border-black/10">
                  <span className="text-black/60">Platform posture</span>
                  <span className="text-black font-medium">{platformStatus}</span>
               </div>
               <div className="flex justify-between p-2 bg-[#f9f9f9] border border-black/10">
                  <span className="text-black/60">Workflow token boundary</span>
                  <span className="text-black font-medium">{platformChecked ? tokenFinding ? 'Widened' : 'No widening found' : 'Unknown'}</span>
               </div>
            </div>
         </div>
         
         <div className="bg-[#111] text-white border border-black p-8 flex flex-col gap-6 relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10 font-mono text-4xl">DRIFT</div>
            <h3 className="font-mono text-[10px] tracking-widest uppercase text-white/40 border-b border-white/10 pb-2 flex items-center gap-2">
              <span className="w-1 h-1 bg-graph-gold rounded-full" />
              {driftFinding ? 'State Drift Detected' : 'State Drift Watch'}
            </h3>
            <p className="text-sm text-white/70 leading-relaxed font-sans">
               {driftFinding?.evidence_summary ?? first?.remediation ?? (platformChecked ? 'Platform and infrastructure findings appear here when posture weakens.' : 'Platform posture has not been checked for this repo. Connected checks require legitify and SCM_TOKEN.')}
            </p>
            <button className="self-start font-mono text-[10px] uppercase border border-white/20 bg-white/5 py-2 px-4 hover:bg-white hover:text-black transition-colors">
               <KeyRound className="inline-block w-3 h-3 mr-2" />
               Posture Check
            </button>
         </div>
      </div>

    </motion.div>
  );
}

function severityRank(severity: string): number {
  return {critical: 5, high: 4, medium: 3, low: 2, info: 1}[severity as 'critical' | 'high' | 'medium' | 'low' | 'info'] ?? 0;
}
