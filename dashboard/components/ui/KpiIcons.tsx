function iconProps(className?: string) {
  return {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: className ?? "h-5 w-5",
  };
}

export function FlameIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M12 2c1 3-2 4-2 7a4 4 0 0 0 8 0c0-1-.3-2-1-3 1.5.6 3 2.6 3 5a6 6 0 0 1-12 0c0-3.5 2-5 4-9Z" />
    </svg>
  );
}

export function DumbbellIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M6.5 6.5 3 10l11 11 3.5-3.5" />
      <path d="M17.5 17.5 21 14 10 3 6.5 6.5" />
      <path d="m15 5 4 4" />
      <path d="m5 15 4 4" />
    </svg>
  );
}

export function DropletIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M12 2.5s6 7 6 11.5a6 6 0 0 1-12 0c0-4.5 6-11.5 6-11.5Z" />
    </svg>
  );
}

export function FootprintsIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="M8 16c1.5 0 2.5-1 2.5-2.5S9 10 8 10s-2.5 1.5-2.5 3.5S6.5 16 8 16Z" />
      <path d="M16 20c1.5 0 2.5-1 2.5-2.5S17.5 14 16 14s-2.5 1.5-2.5 3.5S14.5 20 16 20Z" />
      <path d="M7 10c0-2 1-3 1-5" />
      <path d="M15 14c0-2 1-3 1-5" />
    </svg>
  );
}

export function StarIcon({ className }: { className?: string }) {
  return (
    <svg {...iconProps(className)}>
      <path d="m12 3 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.3 6.8 19l1-5.8-4.3-4.1 5.9-.9L12 3Z" />
    </svg>
  );
}
