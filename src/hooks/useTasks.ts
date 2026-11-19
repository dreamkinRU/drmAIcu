import { useState } from 'react';
import { Task } from '../types';
import { initialTasks } from '../utils/constants';

export function useTasks() {
  const [taskList, setTaskList] = useState<Task[]>(initialTasks);
  const [newTaskText, setNewTaskText] = useState('');
  const [newTaskPriority, setNewTaskPriority] = useState<'high' | 'medium' | 'low'>('medium');
  const [newTaskCategory, setNewTaskCategory] = useState<'code' | 'general'>('general');

  const addTask = () => {
    if (!newTaskText.trim()) return;
    setTaskList(prev => [
      ...prev,
      {
        id: prev.length + 1,
        text: newTaskText,
        done: false,
        priority: newTaskPriority,
        category: newTaskCategory,
      },
    ]);
    setNewTaskText('');
  };

  const toggleTask = (id: number) => {
    setTaskList(prev => prev.map(t => (t.id === id ? { ...t, done: !t.done } : t)));
  };

  const deleteTask = (id: number) => {
    setTaskList(prev => prev.filter(t => t.id !== id));
  };

  const codeTasks = taskList.filter(t => t.category === 'code');
  const generalTasks = taskList.filter(t => t.category === 'general');
  const completedTasks = taskList.filter(t => t.done).length;

  return {
    taskList, setTaskList,
    newTaskText, setNewTaskText,
    newTaskPriority, setNewTaskPriority,
    newTaskCategory, setNewTaskCategory,
    addTask, toggleTask, deleteTask,
    codeTasks, generalTasks, completedTasks,
  };
}
