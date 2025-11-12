import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';

type FeedbackKind = 'success' | 'error' | 'info';

type FeedbackMessage = {
  id: number;
  kind: FeedbackKind;
  text: string;
};

type FeedbackContextValue = {
  notify: (kind: FeedbackKind, text: string) => void;
  notifySuccess: (text: string) => void;
  notifyError: (text: string) => void;
  notifyInfo: (text: string) => void;
};

const FeedbackContext = createContext<FeedbackContextValue | undefined>(undefined);

export function useFeedback(): FeedbackContextValue {
  const value = useContext(FeedbackContext);
  if (!value) {
    throw new Error('useFeedback must be used within a FeedbackProvider');
  }
  return value;
}

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<FeedbackMessage[]>([]);
  const idRef = useRef(0);

  const pushMessage = useCallback((kind: FeedbackKind, text: string) => {
    idRef.current += 1;
    const id = idRef.current;
    setMessages((prev) => [...prev, { id, kind, text }]);
    window.setTimeout(() => {
      setMessages((prev) => prev.filter((msg) => msg.id !== id));
    }, 3200);
  }, []);

  const value = useMemo<FeedbackContextValue>(
    () => ({
      notify: pushMessage,
      notifySuccess: (text: string) => pushMessage('success', text),
      notifyError: (text: string) => pushMessage('error', text),
      notifyInfo: (text: string) => pushMessage('info', text),
    }),
    [pushMessage],
  );

  return (
    <FeedbackContext.Provider value={value}>
      {children}
      <div className="feedback-toast-container" aria-live="polite">
        {messages.map((message) => (
          <div key={message.id} className={`feedback-toast feedback-${message.kind}`}>
            {message.text}
          </div>
        ))}
      </div>
    </FeedbackContext.Provider>
  );
}
