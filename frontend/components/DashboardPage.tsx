"use client";

import SummaryCards from "./SummaryCards";
import TimelineChart from "./TimelineChart";
import TopAuthorsTable from "./TopAuthorsTable";
import WordCloudChart from "./WordCloudChart";
import DateRangePicker from "./DateRangePicker";
import TopMentionsCard from "./TopMentionsCard";
import { DashboardFilterProvider } from "@/context/DashboardFilterContext";

export default function DashboardPage() {
  return (
    <DashboardFilterProvider>
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-black mb-2">Dashboard Overview</h2>
          <p className="text-black">
            Media Monitoring Isu dan sentiment terkait Kementerian UMKM
          </p>
        </div>

        <DateRangePicker />
        <SummaryCards />

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