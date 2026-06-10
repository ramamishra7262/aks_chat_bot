const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

/**
 * Streams a chat completion from the backend over Server-Sent Events.
 *
 * @param {Array<{role: string, content: string}>} messages
 * @param {{namespace?: string, useRag?: boolean, sessionId?: string}} options
 * @param {(event: object) => void} onEvent - called for each parsed SSE event
 * @param {AbortSignal} [signal]
 */
export async function streamChat(messages, options, onEvent, signal) {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: options.sessionId || "default",
      messages,
      namespace: options.namespace,
      use_rag: options.useRag ?? true,
    }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);

      if (!rawEvent.startsWith("data:")) continue;
      const data = rawEvent.slice(5).trim();
      if (data === "[DONE]") return;

      try {
        onEvent(JSON.parse(data));
      } catch (err) {
        console.error("Failed to parse SSE event", err, data);
      }
    }
  }
}

export async function fetchHealth() {
  const response = await fetch(`${API_BASE}/healthz`);
  return response.json();
}
