"use client";

import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Newspaper,
  TrendingUp,
  Menu,
  X,
  Users,
  Brain, // icon untuk halaman Train SVM
} from "lucide-react";
import { useState } from "react";


interface SidebarProps {
  activePage: string;
  onPageChange: (page: string) => void;
  role?: "user" | "admin"; // 👈 support role
}

// 🔥 Menu berdasarkan role
const menuByRole = {
  user: [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
    },
    {
      id: "mentions",
      label: "Mentions",
      icon: Newspaper,
    },
    {
      id: "sentiment",
      label: "Sentiment",
      icon: TrendingUp,
    },
  ],
  admin: [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
    },
    {
      id: "users",
      label: "Users",
      icon: Users, // 👈 khusus admin
    },
    {
      id: "mentions",
      label: "Mention",
      icon: Newspaper,
    },
    {
      id: "sentiment",
      label: "Sentimen",
      icon: TrendingUp,
    },
    {
      id: "svm-train",
      label: "Train SVM",
      icon: Brain, // admin-only: kelola label & retrain SVM
    },
  ],
};

export default function Sidebar({
  activePage,
  onPageChange,
  role = "user",
}: SidebarProps) {
  const [isOpen, setIsOpen] = useState(false);

  const navItems = menuByRole[role]; // 👈 ambil menu sesuai role

  return (
    <>
      {/* 🔹 Mobile Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
      className="fixed top-4 left-4 z-50 p-2 rounded-lg bg-white text-black border border-border lg:hidden"
      >
        {isOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {/* 🔹 Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* 🔹 Sidebar */}
      <aside
        className={cn(
      "fixed top-0 left-0 h-full w-64 bg-white border-r border-sidebar-border z-40 transition-transform duration-300",
          "lg:translate-x-0",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* 🔹 Logo */}
        <div className="flex items-center gap-3 px-6 py-6 border-b border-sidebar-border">
         <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
  <span className="text-black font-bold text-lg">
              {role === "admin" ? "A" : "M"}
            </span>
          </div>

          <div>
            <h1 className="font-semibold text-black">
              {role === "admin" ? "Admin Panel" : "Media Monitoring"}
            </h1>
            <p className="text-xs text-black">
              {role === "admin"
                ? "Administrator"
                : "Kementerian UMKM"}
            </p>
          </div>
        </div>

        {/* 🔹 Navigation */}
        <nav className="p-4 space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;

            return (
             <button
  key={item.id}
  onClick={() => {
    onPageChange(item.id);
    setIsOpen(false);
  }}
  className={cn(
    "w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors text-left",
    isActive
      ? "bg-blue-100 text-blue-700"
      : "text-black hover:bg-blue-100 hover:text-blue-700"
  )}
>
  <Icon size={20} />
  <span className="font-medium">{item.label}</span>
</button>
            );
          })}
        </nav>
      </aside>
    </>
  );
}