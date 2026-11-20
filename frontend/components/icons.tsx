import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;
const base = (p: P) => ({
  width: 16, height: 16, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, ...p,
});

export const IconInfo = (p: P) => (<svg {...base(p)}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>);
export const IconAlert = (p: P) => (<svg {...base(p)}><path d="M12 3 2 20h20L12 3z" /><path d="M12 10v4M12 17h.01" /></svg>);
export const IconCheck = (p: P) => (<svg {...base(p)}><path d="m5 12 4 4 10-10" /></svg>);
export const IconX = (p: P) => (<svg {...base(p)}><path d="M6 6l12 12M18 6 6 18" /></svg>);
export const IconLock = (p: P) => (<svg {...base(p)}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>);
export const IconUnlock = (p: P) => (<svg {...base(p)}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 7.5-2" /></svg>);
export const IconMic = (p: P) => (<svg {...base(p)}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>);
export const IconStop = (p: P) => (<svg {...base(p)}><rect x="6" y="6" width="12" height="12" rx="2" /></svg>);
export const IconMenu = (p: P) => (<svg {...base(p)}><path d="M4 7h16M4 12h16M4 17h16" /></svg>);
export const IconPlus = (p: P) => (<svg {...base(p)}><path d="M12 5v14M5 12h14" /></svg>);
export const IconTrash = (p: P) => (<svg {...base(p)}><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>);
export const IconCopy = (p: P) => (<svg {...base(p)}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a1 1 0 0 1 1-1h9" /></svg>);
export const IconDownload = (p: P) => (<svg {...base(p)}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></svg>);
export const IconRefresh = (p: P) => (<svg {...base(p)}><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7" /></svg>);
export const IconArrowRight = (p: P) => (<svg {...base(p)}><path d="M5 12h14M13 6l6 6-6 6" /></svg>);
export const IconPhone = (p: P) => (<svg {...base(p)}><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" /></svg>);
export const IconSend = (p: P) => (<svg {...base(p)}><path d="M4 12 20 4l-6 16-3-7-7-1z" /></svg>);
export const IconStar = (p: P) => (<svg {...base(p)}><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9L12 3z" /></svg>);

/** The REDUTAX mark: a red block (the extra tokens) being cut down by a blue bar (the measurement). */
export function BrandMark(p: P) {
  return (
    <svg viewBox="0 0 26 26" className="brand-mark" aria-hidden="true" {...p}>
      <rect x="1" y="1" width="24" height="24" rx="5" fill="#C1121F" />
      <rect x="6" y="7" width="14" height="3" rx="1.5" fill="#FFFFFF" />
      <rect x="6" y="12" width="9" height="3" rx="1.5" fill="#FFFFFF" />
      <rect x="6" y="17" width="5" height="3" rx="1.5" fill="#FFFFFF" />
      <rect x="17" y="12" width="3" height="8" rx="1.5" fill="#93AEEB" />
    </svg>
  );
}
