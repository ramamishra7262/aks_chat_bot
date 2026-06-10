import ReactMarkdown from "react-markdown";
import ToolCallDisplay from "./ToolCallDisplay.jsx";
import KubernetesObjectPreview from "./KubernetesObjectPreview.jsx";

export default function MessageBubble({ message }) {
  const { role, content, toolCalls } = message;
  const isUser = role === "user";

  return (
    <div className={`message ${isUser ? "user" : "assistant"}`}>
      <div className="avatar">{isUser ? "You" : "AI"}</div>
      <div className="bubble">
        {toolCalls && toolCalls.length > 0 && (
          <div className="tool-calls">
            {toolCalls.map((tc, i) => (
              <div key={i}>
                <ToolCallDisplay toolCall={tc} />
                <KubernetesObjectPreview toolName={tc.tool_name} args={tc.arguments} />
              </div>
            ))}
          </div>
        )}
        {content && (
          isUser ? <span>{content}</span> : <ReactMarkdown>{content}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
