import clsx from 'clsx';

interface SkeletonCardProps {
  width?: string;
  height?: string;
  lines?: number;
  gap?: string;
}

export function SkeletonCard({ width = '100%', height = 'auto', lines = 2, gap = '0.6rem' }: SkeletonCardProps) {
  return (
    <div
      className="skeleton-card"
      style={{
        width,
        height,
        display: 'flex',
        flexDirection: 'column',
        gap,
      }}
    >
      {Array.from({ length: lines }).map((_, index) => (
        <span
          key={index}
          className={clsx('skeleton', index === 0 && 'skeleton-strong')}
          style={{ width: index === 0 ? '60%' : '100%', height: index === 0 ? '1rem' : '0.8rem' }}
        />
      ))}
    </div>
  );
}
