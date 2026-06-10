import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble.jsx";

const SUGGESTIONS = [
  "Why are pods crash-looping in the app namespace?",
  "Show me unhealthy pods in default",
  "Scale the api deployment to 4 replicas",
  "Create a ConfigMap named feature-flags with KEY=true",
];

export default function ChatWindow({ messages, onSuggestion }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="chat-container">
        <div className="empty-state">
          <h2>AKS Copilot</h2>
          <p>Ask about cluster health, troubleshoot failures, or create Kubernetes objects.</p>
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => onSuggestion(s)}>{s}</button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-container">
      {messages.map((m, i) => (
        <MessageBubble key={i} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
