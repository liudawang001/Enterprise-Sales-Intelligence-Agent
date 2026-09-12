import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { WorkspacePage } from "./pages/WorkspacePage";
import { ExportsPage } from "./pages/ExportsPage";
import "./styles.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 5_000, retry: 1 } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><Routes>
    <Route path="/workspace" element={<WorkspacePage />} />
    <Route path="/tasks/:taskId" element={<WorkspacePage />} />
    <Route path="/tasks" element={<Navigate to="/workspace" replace />} />
    <Route path="/exports" element={<ExportsPage />} />
    <Route path="*" element={<Navigate to="/workspace" replace />} />
  </Routes></BrowserRouter></QueryClientProvider></StrictMode>
);
