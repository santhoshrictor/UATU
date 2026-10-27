'use client';
import { ArrowRight } from 'lucide-react';

export interface FlowButtonProps {
  text?: string;
  onClick?: () => void;
  className?: string;
}

export function FlowButton({ text = "Ask IRIS AI", onClick, className = "" }: FlowButtonProps) {
  return (
    <button 
      onClick={onClick}
      className={`group relative flex items-center justify-center gap-1 overflow-hidden rounded-[100px] border-[1.5px] border-emerald-500/40 bg-transparent px-6 py-2.5 text-xs font-semibold text-emerald-400 cursor-pointer transition-all duration-[600ms] ease-[cubic-bezier(0.23,1,0.32,1)] hover:border-transparent hover:text-white hover:rounded-[12px] active:scale-[0.95] ${className}`}
    >
      {/* Left arrow */}
      <ArrowRight 
        className="absolute w-3.5 h-3.5 left-[-25%] stroke-emerald-400 fill-none z-[9] group-hover:left-3.5 group-hover:stroke-white transition-all duration-[800ms] ease-[cubic-bezier(0.34,1.56,0.64,1)]" 
      />

      {/* Text */}
      <span className="relative z-[1] -translate-x-2.5 group-hover:translate-x-2.5 transition-all duration-[800ms] ease-out">
        {text}
      </span>

      {/* Expanding Circle Fill */}
      <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-4 h-4 bg-emerald-600 rounded-[50%] opacity-0 group-hover:w-[260px] group-hover:h-[260px] group-hover:opacity-100 transition-all duration-[800ms] ease-[cubic-bezier(0.19,1,0.22,1)]"></span>

      {/* Right arrow */}
      <ArrowRight 
        className="absolute w-3.5 h-3.5 right-3.5 stroke-emerald-400 fill-none z-[9] group-hover:right-[-25%] group-hover:stroke-white transition-all duration-[800ms] ease-[cubic-bezier(0.34,1.56,0.64,1)]" 
      />
    </button>
  );
}

export default FlowButton;
