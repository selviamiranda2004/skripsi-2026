"use client";

import SummaryCards from "./SummaryCards";
import TimelineChart from "./TimelineChart";
import TopAuthorsTable from "./TopAuthorsTable";
import WordCloudChart from "./WordCloudChart";
import DateRangePicker from "./DateRangePicker";
import TopMentionsCard from "./TopMentionsCard";
import { DashboardFilterProvider } from "@/context/DashboardFilterContext";

export default function AdminDashboardPage() {
  return (
    <DashboardFilterProvider>
      <div className="min-h-screen bg-white text-black p-6 space-y-6">
        <h2 className="text-2xl font-bold text-black">Admin Dashboard</h2>

        {/* Date range filter — ngendaliin semua chart di bawahnya */}
        <DateRangePicker />

        <SummaryCards role="admin" />

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <TimelineChart />
          <TopAuthorsTable />
        </div>

        <TopMentionsCard />

        <WordCloudChart />
      </div>
    </DashboardFilterProvider>
  );
}