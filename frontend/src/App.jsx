import { useState, useRef, useCallback } from "react";
import ChatWindow from "./components/ChatWindow.jsx";
import { streamChat } from "./services/api.js";

const NAMESPACES = ["default", "app", "monitoring", "ingress-nginx", "kube-system"];

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [namespace, setNamespace] = useState("app");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef(null);

  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    const namespaceHint = `[Active namespace: ${namespace}] `;
    const userMessage = { role: "user", content: trimmed };
    const assistantMessage = { role: "assistant", content: "", toolCalls: [] };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
    setIsStreaming(true);

    const history = [...messages, { role: "user", content: namespaceHint + trimmed }].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        history,
        { namespace, useRag: true, sessionId: "web-session" },
        (event) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = { ...updated[updated.length - 1] };
            last.toolCalls = last.toolCalls ? [...last.toolCalls] : [];

            if (event.type === "token") {
              last.content = (last.content || "") + event.content;
            } else if (event.type === "tool_call") {
              const idx = last.toolCalls.findIndex(
                (tc) => tc.tool_name === event.tool_name && tc.status === "started" && event.status !== "started"
              );
              if (idx >= 0) {
                last.toolCalls[idx] = { ...last.toolCalls[idx], ...event };
              } else {
                last.toolCalls.push(event);
              }
            }

            updated[updated.length - 1] = last;
            return updated;
          });
        },
        controller.signal
      );
    } catch (err) {
      console.error(err);
      setMessages((prev) => {
        const updated = [...prev];
        const last = { ...updated[updated.length - 1] };
        last.content = (last.content || "") + `\n\n_Error: ${err.message}_`;
        updated[updated.length - 1] = last;
        return updated;
      });
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [messages, namespace, isStreaming]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>
          AKS Copilot <span className="badge">Azure OpenAI + AI Search</span>
        </h1>
        <select
          className="namespace-select"
          value={namespace}
          onChange={(e) => setNamespace(e.target.value)}
        >
          {NAMESPACES.map((ns) => (
            <option key={ns} value={ns}>{ns}</option>
          ))}
        </select>
      </header>

      <ChatWindow messages={messages} onSuggestion={sendMessage} />

      <div className="composer">
        <textarea
          placeholder="Ask AKS Copilot to diagnose, fix, or create Kubernetes resources..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
        />
        <button onClick={() => sendMessage(input)} disabled={isStreaming || !input.trim()}>
          {isStreaming ? "Thinking..." : "Send"}
        </button>
      </div>
    </div>
  );
}
