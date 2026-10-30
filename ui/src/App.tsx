import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DataProvider } from "./data";
import { AttackExplorer } from "./views/AttackExplorer";
import { Overview } from "./views/Overview";
import { PolicyView } from "./views/PolicyView";
import { ReportView } from "./views/ReportView";
import { RunDetail } from "./views/RunDetail";

export default function App() {
  return (
    <BrowserRouter>
      <DataProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="run" element={<RunDetail />} />
            <Route path="attacks" element={<AttackExplorer />} />
            <Route path="policy" element={<PolicyView />} />
            <Route path="report" element={<ReportView />} />
            <Route path="*" element={<div className="empty-state"><h2>Not found</h2><p>Use the sidebar to return to a view.</p></div>} />
          </Route>
        </Routes>
      </DataProvider>
    </BrowserRouter>
  );
}
