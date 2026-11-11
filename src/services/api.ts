const API_BASE = "http://localhost:8000";

export async function getHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export async function getServices() {
  const res = await fetch(`${API_BASE}/services`);
  return res.json();
}

export async function startService(name: string) {
  const res = await fetch(`${API_BASE}/start/${name}`, { method: "POST" });
  return res.json();
}