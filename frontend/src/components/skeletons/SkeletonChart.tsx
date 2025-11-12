interface SkeletonChartProps {
  height?: number;
  bars?: number;
}

export function SkeletonChart({ height = 240, bars = 6 }: SkeletonChartProps) {
  const barWidth = `${100 / (bars * 2)}%`;
  return (
    <div
      style={{
        position: 'relative',
        height,
        display: 'flex',
        alignItems: 'flex-end',
        gap: '1rem',
        padding: '1rem',
        borderRadius: 'var(--radius-lg)',
        background: 'rgba(15,23,42,0.5)',
        border: '1px solid rgba(148,163,184,0.08)',
      }}
    >
      {Array.from({ length: bars }).map((_, index) => (
        <div
          key={index}
          className="skeleton"
          style={{
            width: barWidth,
            height: `${60 + Math.random() * 40}%`,
            borderRadius: '0.6rem',
          }}
        />
      ))}
    </div>
  );
}
