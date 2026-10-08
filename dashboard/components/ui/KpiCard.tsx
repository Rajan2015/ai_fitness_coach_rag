export function KpiCard({
  label,
  value,
  hint,
  icon,
  accentClassName = "bg-brand-light text-brand",
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: React.ReactNode;
  accentClassName?: string;
}) {
  return (
    <div className="flex items-start gap-3 border border-[#d8e3dd] bg-white p-5 shadow-[0_8px_24px_rgba(6,63,59,0.06)]">
      {icon && (
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${accentClassName}`}>
          {icon}
        </div>
      )}
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#638076]">{label}</p>
        <p className="mt-2 text-2xl font-semibold tracking-tight text-[#102a28]">{value}</p>
        {hint && <p className="mt-1 text-xs text-[#638076]">{hint}</p>}
      </div>
    </div>
  );
}
