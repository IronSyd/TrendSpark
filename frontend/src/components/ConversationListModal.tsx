import AutoSizer from 'react-virtualized-auto-sizer';
import { FixedSizeList as List } from 'react-window';
import type { ListChildComponentProps } from 'react-window';

import type { Conversation } from '../types';

interface ConversationListModalProps {
  conversations: Conversation[];
  onClose: () => void;
  onSelect?: (item: Conversation) => void;
  lastUpdated?: Date | null;
}

const CARD_MIN_WIDTH = 260;
const GRID_GAP = 16;
const ROW_HEIGHT = 248;

type RowData = {
  conversations: Conversation[];
  itemsPerRow: number;
  onSelect?: (item: Conversation) => void;
};

function ConversationRow({ index, style, data }: ListChildComponentProps<RowData>) {
  const { conversations, itemsPerRow, onSelect } = data;
  const start = index * itemsPerRow;
  const cards = [];

  for (let offset = 0; offset < itemsPerRow; offset += 1) {
    const conversation = conversations[start + offset];
    if (!conversation) {
      break;
    }

    cards.push(
      <article
        key={`${conversation.platform}-${conversation.post_id}`}
        className="conversation-card"
        onClick={() => onSelect?.(conversation)}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onSelect?.(conversation);
          }
        }}
        style={{ cursor: onSelect ? 'pointer' : 'default' }}
      >
        <header>
          <span className={`platform-badge ${conversation.platform === 'x' ? 'x' : conversation.platform}`}>
            {conversation.platform === 'x' ? 'X' : conversation.platform}
          </span>
          <div className="conversation-metrics">
            <span className="metric-chip">Virality {conversation.virality.toFixed(2)}</span>
            <span className="metric-chip">Velocity {conversation.velocity.toFixed(2)}</span>
            {conversation.trending && (
              <span className="metric-chip" style={{ background: 'rgba(52, 211, 153, 0.16)', color: '#34d399' }}>
                Trending
              </span>
            )}
          </div>
        </header>
        <div>
          <p className="title">{conversation.text.split('\n')[0]}</p>
          {conversation.text.split('\n').slice(1).map((line: string, idx: number) => (
            <p key={idx}>{line}</p>
          ))}
        </div>
        <div className="conversation-metrics">
          {conversation.url && (
            <a
              href={conversation.url}
              target="_blank"
              rel="noreferrer"
              onClick={(event) => event.stopPropagation()}
              className="metric-chip"
            >
              Open thread
            </a>
          )}
          <span className="metric-chip">ID {conversation.post_id}</span>
        </div>
        {conversation.replies?.length ? (
          <div className="suggestions">
            {conversation.replies.slice(0, 2).map((reply, idx: number) => (
              <span key={idx} className="suggestion-pill">
                {reply.tone && <small>{reply.tone}</small>}
                <span>{reply.reply}</span>
              </span>
            ))}
          </div>
        ) : (
          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No suggestions yet</span>
        )}
      </article>
    );
  }

  return (
    <div
      style={{
        ...style,
        width: style.width,
        display: 'grid',
        gridTemplateColumns: `repeat(${data.itemsPerRow}, minmax(${CARD_MIN_WIDTH}px, 1fr))`,
        gap: GRID_GAP,
        paddingRight: GRID_GAP,
        boxSizing: 'border-box',
      }}
    >
      {cards}
    </div>
  );
}

export function ConversationListModal({ conversations, onClose, onSelect, lastUpdated }: ConversationListModalProps) {
  if (!conversations.length) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div
        className="modal"
        style={{ maxWidth: '960px', maxHeight: '90vh', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ margin: 0 }}>Full trending board</h2>
            {lastUpdated && (
              <small style={{ color: 'var(--text-muted)' }}>Updated {lastUpdated.toLocaleTimeString()}</small>
            )}
          </div>
          <button className="button" onClick={onClose} type="button" style={{ background: 'rgba(148,163,184,0.18)' }}>
            Close
          </button>
        </div>

        <div style={{ flex: '1 1 auto', minHeight: 320 }}>
          <AutoSizer disableHeight={false}>
            {({ height, width }) => {
              const itemsPerRow = Math.max(1, Math.floor((width + GRID_GAP) / (CARD_MIN_WIDTH + GRID_GAP)));
              const rowCount = Math.ceil(conversations.length / itemsPerRow);
              const itemData: RowData = { conversations, itemsPerRow, onSelect };

              return (
                <List
                  height={height}
                  width={width}
                  itemCount={rowCount}
                  itemSize={ROW_HEIGHT}
                  itemData={itemData}
                  overscanCount={2}
                >
                  {ConversationRow}
                </List>
              );
            }}
          </AutoSizer>
        </div>
      </div>
    </div>
  );
}
