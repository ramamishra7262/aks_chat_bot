/**
 * Renders a YAML-ish preview for create_* tool calls so the user can see
 * exactly what manifest the bot is about to (or did) apply.
 */
export default function KubernetesObjectPreview({ toolName, args }) {
  if (!toolName.startsWith("create_")) return null;

  const kind = toolName.replace("create_", "");
  const lines = [`apiVersion: ...`, `kind: ${kind.charAt(0).toUpperCase() + kind.slice(1)}`, `metadata:`, `  name: ${args.name}`, `  namespace: ${args.namespace}`];

  if (args.image) lines.push(`spec:`, `  image: ${args.image}`);
  if (args.replicas) lines.push(`  replicas: ${args.replicas}`);

  return (
    <pre style={{ marginTop: 8 }}>
      <code>{lines.join("\n")}</code>
    </pre>
  );
}
