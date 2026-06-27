"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import DashboardPage from "@/components/DashboardPage";
import MentionsPage from "@/components/MentionsPage";
import SentimentPage from "@/components/SentimentPage";

export default function Home() {
  const [activePage, setActivePage] = useState("dashboard");
  const { user, logout, isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;

    if (!isAuthenticated) {
      router.push("/login");
      return;
    }

    if (user?.role === "admin") {
      router.push("/admin");
    }
  }, [user, loading, isAuthenticated, router]);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const renderPage = () => {
    switch (activePage) {
      case "dashboard": return <DashboardPage />;
      case "mentions": return <MentionsPage />;
      case "sentiment": return <SentimentPage />;
      default: return <DashboardPage />;
    }
  };

  const getPageTitle = () => {
    switch (activePage) {
      case "dashboard": return "Dashboard";
      case "mentions": return "Mentions";
      case "sentiment": return "Sentiment Analysis";
      default: return "Dashboard";
    }
  };

  if (loading || !isAuthenticated || user?.role === "admin") {
    return null;
  }

  return (
    <div className="min-h-screen bg-white">
      <Sidebar activePage={activePage} onPageChange={setActivePage} />

      <main className="lg:ml-64 min-h-screen">
        <header className="sticky top-0 z-20 bg-white backdrop-blur-sm border-b border-border px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 lg:gap-0">
              <div className="w-10 lg:hidden" />
              <h1 className="text-xl font-semibold text-black">
                {getPageTitle()}
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-black hidden sm:block">
                {user?.username} ({user?.role})
              </span>
              <button
                onClick={handleLogout}
                className="px-3 py-1 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        <div className="p-6">{renderPage()}</div>
      </main>
    </div>
  );
}