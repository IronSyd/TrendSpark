interface SkeletonListProps {
  rows?: number;
  columns?: number;
  rowHeight?: string;
  gap?: string;
}

export function SkeletonList({
  rows = 5,
  columns = 1,
  rowHeight = '1rem',
  gap = '0.75rem',
}: SkeletonListProps) {
  return (
    <div style={{ display: 'grid', gap, gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton" style={{ height: rowHeight, borderRadius: '0.6rem' }} />
      ))}
    </div>
  );
}
