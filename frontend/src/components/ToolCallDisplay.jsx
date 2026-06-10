import { useState } from "react";

function formatResult(result) {
  if (result === undefined || result === null) return "";
  if (typeof result === "string") return result;
  try {
    return JSON.stringify(result, null, 2);
  } catch {
    return String(result);
  }
}

export default function ToolCallDisplay({ toolCall }) {
  const [open, setOpen] = useState(false);
  const { tool_name: name, arguments: args, status, result } = toolCall;

  return (
    <div className={`tool-call status-${status}`}>
      <div className="tool-call-header" onClick={() => setOpen((o) => !o)}>
        <span className="status-dot" />
        <span>
          {status === "started" && "Calling "}
          {status === "completed" && "Called "}
          {status === "failed" && "Failed "}
          <strong>{name}</strong>
          {args && Object.keys(args).length > 0 && (
            <span style={{ opacity: 0.7 }}>
              ({Object.entries(args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
            </span>
          )}
        </span>
        <span style={{ marginLeft: "auto" }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div className="tool-call-body">
          {result !== undefined ? formatResult(result) : "Waiting for result..."}
        </div>
      )}
    </div>
  );
}
