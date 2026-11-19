import React from 'react';
import { TabId } from '../../types';

interface TabLayoutProps {
  activeTab: TabId;
  children: React.ReactNode;
}

export default function TabLayout({ activeTab, children }: TabLayoutProps) {
  return (
    <main className="flex-1 max-w-7xl mx-auto px-4 py-6 w-full pb-16">
      {children}
    </main>
  );
}
