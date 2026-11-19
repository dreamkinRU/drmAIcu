import { Task } from '../../types';

interface TasksTabProps {
  taskList: Task[];
  newTaskText: string;
  setNewTaskText: (value: string) => void;
  newTaskPriority: 'high' | 'medium' | 'low';
  setNewTaskPriority: (value: 'high' | 'medium' | 'low') => void;
  newTaskCategory: 'code' | 'general';
  setNewTaskCategory: (value: 'code' | 'general') => void;
  addTask: () => void;
  toggleTask: (id: number) => void;
  deleteTask: (id: number) => void;
  codeTasks: Task[];
  generalTasks: Task[];
}

function TaskRow({
  task,
  onToggle,
  onDelete,
}: {
  task: Task;
  onToggle: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex items-center gap-3 py-3 border-b border-gray-800/50 last:border-0">
      <button
        onClick={onToggle}
        className={`w-6 h-6 rounded border-2 flex items-center justify-center ${
          task.done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-gray-600'
        }`}
      >
        {task.done && '✓'}
      </button>
      <span className={`text-sm flex-1 ${task.done ? 'text-gray-500 line-through' : 'text-gray-200'}`}>
        {task.text}
      </span>
      <span
        className={`px-2 py-1 rounded text-xs font-bold ${
          task.priority === 'high'
            ? 'bg-red-500/20 text-red-400'
            : task.priority === 'medium'
            ? 'bg-yellow-500/20 text-yellow-400'
            : 'bg-gray-500/20 text-gray-400'
        }`}
      >
        {task.priority.toUpperCase()}
      </span>
      <button onClick={onDelete} className="text-red-400 hover:text-red-300 text-sm">
        ✕
      </button>
    </div>
  );
}

export default function TasksTab({
  taskList, newTaskText, setNewTaskText,
  newTaskPriority, setNewTaskPriority,
  newTaskCategory, setNewTaskCategory,
  addTask, toggleTask, deleteTask,
  codeTasks, generalTasks,
}: TasksTabProps) {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Задачи</h2>

      <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
        <h3 className="text-lg font-bold mb-4">➕ Добавить задачу</h3>
        <div className="space-y-3">
          <input
            type="text"
            value={newTaskText}
            onChange={(e) => setNewTaskText(e.target.value)}
            placeholder="Описание задачи..."
            className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none"
          />
          <div className="flex gap-3">
            <select
              value={newTaskPriority}
              onChange={(e) => setNewTaskPriority(e.target.value as any)}
              className="px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm"
            >
              <option value="high">🔴 Высокий</option>
              <option value="medium">🟡 Средний</option>
              <option value="low">🔵 Низкий</option>
            </select>
            <select
              value={newTaskCategory}
              onChange={(e) => setNewTaskCategory(e.target.value as any)}
              className="px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm"
            >
              <option value="code">⟨⟩ Исправление кода</option>
              <option value="general">📋 Общая задача</option>
            </select>
            <button
              onClick={addTask}
              className="px-6 py-2 rounded-lg bg-emerald-500 text-white text-sm font-bold"
            >
              Добавить
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6">
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
          <span>⟨⟩</span> Задачи по коду ({codeTasks.filter(t => !t.done).length})
        </h3>
        <div className="space-y-3">
          {codeTasks.map(task => (
            <TaskRow
              key={task.id}
              task={task}
              onToggle={() => toggleTask(task.id)}
              onDelete={() => deleteTask(task.id)}
            />
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-6">
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
          <span>📋</span> Общие задачи ({generalTasks.filter(t => !t.done).length})
        </h3>
        <div className="space-y-3">
          {generalTasks.map(task => (
            <TaskRow
              key={task.id}
              task={task}
              onToggle={() => toggleTask(task.id)}
              onDelete={() => deleteTask(task.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
