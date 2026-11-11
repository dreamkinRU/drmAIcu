import { useEffect, useState } from "react";
import { getServices, startService } from "../services/api";
import { StatusCard } from "../components/StatusCard";

export default function Dashboard() {
  const [services, setServices] = useState<any>(null);

  useEffect(() => {
    // Обновляем статус каждые 3 секунды
    const interval = setInterval(() => {
      getServices().then(setServices);
    }, 3000);
    getServices().then(setServices);
    return () => clearInterval(interval);
  }, []);

  if (!services) return <div>Загрузка...</div>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">🤖 Control Panel</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <StatusCard
          name="Ollama"
          status={services.ollama?.status}
          onAction={() => window.open("http://localhost:11434")}
        />
        <StatusCard
          name="Frontend"
          status={services.frontend?.status}
        />
        <StatusCard
          name="Agent (Python)"
          status={services.agent?.status}
          onAction={() => startService("agent")}
        />
      </div>

      {/* Здесь будут логи, кнопки, и т.д. */}
    </div>
  );
}