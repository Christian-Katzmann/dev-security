import {Play, SlidersHorizontal} from 'lucide-react';
import {motion} from 'motion/react';

type EmptyRepoStateProps = {
  repoName: string;
  onQuickCheck: () => void;
  onChooseChecks: () => void;
  isRunning: boolean;
};

export default function EmptyRepoState({repoName, onQuickCheck, onChooseChecks, isRunning}: EmptyRepoStateProps) {
  return (
    <motion.div
      initial={{opacity: 0, y: 10}}
      animate={{opacity: 1, y: 0}}
      exit={{opacity: 0, scale: 0.98}}
      className="p-6 md:p-12 max-w-[1400px] w-full min-h-[520px] flex items-center"
    >
      <section className="w-full border border-black/10 bg-white/55 backdrop-blur-sm px-6 py-8 md:px-10 md:py-12 relative overflow-hidden">
        <div className="absolute inset-y-0 right-0 w-1/2 pointer-events-none opacity-50">
          <svg viewBox="0 0 600 500" className="w-full h-full" preserveAspectRatio="none">
            <path d="M80 420 C220 120 360 520 540 90" fill="none" stroke="rgba(0,0,0,0.08)" strokeWidth="1" />
            <path d="M110 450 C250 170 390 480 560 140" fill="none" stroke="rgba(212,166,45,0.28)" strokeWidth="1" />
            <path d="M160 470 C280 220 430 430 590 210" fill="none" stroke="rgba(0,0,0,0.05)" strokeWidth="1" />
          </svg>
        </div>

        <div className="relative z-10 max-w-2xl">
          <p className="font-mono text-[10px] tracking-[0.3em] uppercase text-black/40 mb-4">
            No Scan Yet
          </p>
          <h2 className="text-4xl md:text-5xl font-light tracking-tight text-black mb-5">
            No scan yet for {repoName}
          </h2>
          <p className="text-sm md:text-base text-black/60 leading-relaxed max-w-xl mb-8">
            This repo is in the target list, but the observatory has not checked it yet. Start with a quick safety sweep to get a practical list of what needs attention.
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            <button
              type="button"
              onClick={onQuickCheck}
              disabled={isRunning}
              className="inline-flex items-center justify-center gap-2 border border-black bg-black text-white px-4 py-3 font-mono text-[10px] uppercase tracking-widest hover:bg-[#222] transition-colors disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5" strokeWidth={1.5} />
              {isRunning ? 'Checking...' : 'Run quick safety sweep'}
            </button>
            <button
              type="button"
              onClick={onChooseChecks}
              disabled={isRunning}
              className="inline-flex items-center justify-center gap-2 border border-black/10 bg-white/50 px-4 py-3 font-mono text-[10px] uppercase tracking-widest hover:border-black/30 transition-colors disabled:opacity-50"
            >
              <SlidersHorizontal className="w-3.5 h-3.5" strokeWidth={1.5} />
              Choose checks
            </button>
          </div>
        </div>
      </section>
    </motion.div>
  );
}
