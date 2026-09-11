import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { WorkspacePage } from "./WorkspacePage";
import { leadPage, task, versions } from "../test/fixtures";
import { useTaskEvents } from "../hooks/useTaskEvents";

class MockEventSource {
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(_url: string) {}
  close() {}
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("historical URL fetches and exports the viewed task version", async () => {
  vi.stubGlobal("EventSource", MockEventSource);
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    let payload: unknown = {};
    if (path === "/api/tasks") payload = [task];
    else if (path === `/api/tasks/${task.task_id}`) payload = { task: { version: 5 }, summary: task };
    else if (path.endsWith("/versions")) payload = versions;
    else if (path.includes("/versions/3/leads")) payload = { ...leadPage, task_version: 3 };
    else if (path === "/api/exports/fields") payload = { items: [] };
    else if (path.endsWith("/exports")) payload = { items: [], count: 0 };
    else if (path.endsWith("/events")) payload = { task_id: task.task_id, task_version: 5, stage: "COMPLETED", status: "COMPLETED", progress: { event: "FINAL", stage: "COMPLETED" } };
    return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/tasks/${task.task_id}?version=3`]}><Routes><Route path="/tasks/:taskId" element={<WorkspacePage />} /></Routes></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText("Historical Version · 只读查看 v3")).toBeInTheDocument();
  await waitFor(() => expect(requests.some((path) => path.includes("/versions/3/leads"))).toBe(true));
  expect(screen.queryByLabelText("对话输入")).not.toBeInTheDocument();
});

test("task events recover terminal state through status API after disconnect", async () => {
  let source: RecoverableEventSource | undefined;
  class RecoverableEventSource {
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: (() => void) | null = null;
    closed = false;
    constructor(_url: string) { source = this; }
    close() { this.closed = true; }
  }
  vi.stubGlobal("EventSource", RecoverableEventSource);
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({
    task_id: "task-1",
    task_version: 2,
    stage: "COMPLETED",
    status: "COMPLETED",
    progress: { event: "FINAL", stage: "COMPLETED" },
  }), { status: 200, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);

  const { result } = renderHook(() => useTaskEvents("task-1"));
  await waitFor(() => expect(result.current?.event).toBe("FINAL"));
  source?.onerror?.();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(source?.closed).toBe(true);
});
