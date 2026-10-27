import React from 'react';

interface UATULogoProps {
  className?: string;
  showSubtitle?: boolean;
}

export const UATULogo: React.FC<UATULogoProps> = ({ className = '', showSubtitle = true }) => {
  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      {/* Geometric Delta / Emblem matching reference screenshot */}
      <div className="relative w-10 h-10 shrink-0 flex items-center justify-center">
        <svg
          viewBox="0 0 48 48"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-10 h-10 drop-shadow-[0_0_12px_rgba(37,99,235,0.45)]"
        >
          <defs>
            <linearGradient id="uatuDeltaGrad" x1="6" y1="42" x2="38" y2="6" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#1d4ed8" />
              <stop offset="50%" stopColor="#2563eb" />
              <stop offset="100%" stopColor="#38bdf8" />
            </linearGradient>
            <linearGradient id="uatuInnerGrad" x1="18" y1="20" x2="30" y2="34" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#0b132b" />
              <stop offset="100%" stopColor="#080e22" />
            </linearGradient>
          </defs>
          {/* Rounded Triangular Delta Outer Shell */}
          <path
            d="M21.2679 7.5C22.6143 5.16795 25.3857 5.16795 26.7321 7.5L43.1865 36C44.5329 38.3321 43.1473 41.25 40.4545 41.25H7.54552C4.85272 41.25 3.46709 38.3321 4.8135 36L21.2679 7.5Z"
            fill="url(#uatuDeltaGrad)"
          />
          {/* Inner Negative Space Opening */}
          <path
            d="M23.134 19.5C23.5189 18.8333 24.4811 18.8333 24.866 19.5L32.6603 33C33.0452 33.6667 32.564 34.5 31.7942 34.5H16.2058C15.436 34.5 14.9548 33.6667 15.3397 33L23.134 19.5Z"
            fill="url(#uatuInnerGrad)"
          />
          {/* Subtle center energy core */}
          <circle cx="24" cy="27" r="2" fill="#38bdf8" className="animate-pulse" />
        </svg>
      </div>

      {/* Brand Typography */}
      <div className="flex flex-col">
        <span className="font-sans text-xl font-extrabold tracking-wider text-white leading-none">
          UATU
        </span>
        {showSubtitle && (
          <span className="text-[8px] font-medium tracking-tight text-slate-400 uppercase mt-1 leading-tight max-w-[155px]">
            UNIFIED ASSISTANT FOR THREAT &amp; UNDERSTANDING
          </span>
        )}
      </div>
    </div>
  );
};

export default UATULogo;
