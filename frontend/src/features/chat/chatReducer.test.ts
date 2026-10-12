import { describe, expect, it } from "vitest";

import type { AgentChatResponse } from "@/api/types";

import { chatReducer, initialChatState, isStoppable, type ChatState } from "./chatReducer";
import type { AssistantMessage } from "./types";

const awaiting: AgentChatResponse = {
  response: "Approval needed: ... Approve or reject it with POST /api/agent/runs/run-1/approval.",
  sources: [],
  run_id: "run-1",
  route: "knowledge_base",
  status: "awaiting_approval",
  approval: [{ tool_call_id: "t1", action: "delete_document", document_id: "doc-1", source: "notes.md", found: true }],
};

function submitted(mode: "agent" | "stream" = "agent"): ChatState {
  return chatReducer(initialChatState, {
    type: "submit",
    conversationId: "c1",
    userId: "u1",
    assistantId: "a1",
    prompt: "hi",
    mode,
    now: 0,
  });
}

const assistant = (state: ChatState) => state.messages.find((message) => message.id === "a1") as AssistantMessage;

describe("chatReducer", () => {
  it("adds the user message and a pending assistant message to the conversation", () => {
    const state = submitted();
    expect(state.conversationId).toBe("c1");
    expect(state.messages.map((message) => message.role)).toEqual(["user", "assistant"]);
    expect(assistant(state).status).toBe("pending");
  });

  it("lets a pending agent reply be stopped and marks it stopped", () => {
    const state = submitted("agent");
    expect(isStoppable(assistant(state))).toBe(true);

    const stopped = chatReducer(state, { type: "streamFinished", id: "a1", outcome: "aborted" });
    expect(assistant(stopped).status).toBe("stopped");
    expect(isStoppable(assistant(stopped))).toBe(false);
  });

  it("only offers Stop for replies still in progress", () => {
    expect(isStoppable(assistant(submitted("stream")))).toBe(true);
    expect(isStoppable(undefined)).toBe(false);
    expect(isStoppable({ id: "u", role: "user", content: "hi" })).toBe(false);

    const done = chatReducer(submitted(), {
      type: "agentResolved",
      id: "a1",
      response: { ...awaiting, status: "completed", approval: null, response: "Done" },
    });
    expect(isStoppable(assistant(done))).toBe(false);
    expect(isStoppable(assistant(chatReducer(submitted(), { type: "agentResolved", id: "a1", response: awaiting })))).toBe(false);
  });

  it("stores agent metadata on completion", () => {
    const state = chatReducer(submitted(), {
      type: "agentResolved",
      id: "a1",
      response: { ...awaiting, status: "completed", approval: null, response: "Done", sources: [{ document_id: "d", text: "t" }] },
    });

    expect(assistant(state)).toMatchObject({ status: "completed", content: "Done", route: "knowledge_base", runId: "run-1" });
    expect(assistant(state).sources).toHaveLength(1);
  });

  it("opens an approval and resolves it with the final answer", () => {
    let state = chatReducer(submitted(), { type: "agentResolved", id: "a1", response: awaiting });
    expect(assistant(state).status).toBe("awaiting_approval");
    expect(assistant(state).approvalState).toEqual({ phase: "idle" });

    state = chatReducer(state, { type: "approvalSubmitting", id: "a1", approved: true });
    state = chatReducer(state, {
      type: "approvalResolved",
      id: "a1",
      approved: true,
      response: { ...awaiting, status: "completed", approval: null, response: "Deleted notes.md." },
    });

    expect(assistant(state)).toMatchObject({ status: "completed", content: "Deleted notes.md." });
    expect(assistant(state).approvalState).toEqual({ phase: "resolved", approved: true });
    expect(assistant(state).approval).toHaveLength(1);
  });

  it("closes an approval the server no longer accepts", () => {
    let state = chatReducer(submitted(), { type: "agentResolved", id: "a1", response: awaiting });
    state = chatReducer(state, { type: "approvalFailed", id: "a1", error: "Expired", closed: true });

    expect(assistant(state).approvalState).toEqual({ phase: "closed", reason: "Expired" });
  });

  it("keeps partial streamed text when the stream is interrupted", () => {
    let state = chatReducer(submitted("stream"), { type: "append", id: "a1", text: "Part" });
    state = chatReducer(state, { type: "streamFinished", id: "a1", outcome: "interrupted" });

    expect(assistant(state)).toMatchObject({ status: "interrupted", content: "Part" });
    expect(assistant(state).error).toMatch(/interrupted/);
  });

  it("resets an assistant message for retry", () => {
    let state = chatReducer(submitted(), { type: "failed", id: "a1", error: "Boom" });
    state = chatReducer(state, { type: "retry", id: "a1", now: 5 });

    expect(assistant(state)).toMatchObject({ status: "pending", content: "", error: undefined, startedAt: 5 });
  });

  it("loads a saved conversation as a thread that can be continued", () => {
    let state = chatReducer(submitted(), { type: "loadStarted", conversationId: "c2" });
    expect(state).toMatchObject({ conversationId: "c2", messages: [], load: { status: "loading" } });

    state = chatReducer(state, {
      type: "loadSucceeded",
      conversationId: "c2",
      now: 0,
      items: [
        { id: "h1", message: "Q1", response: "A1", model: "m", created_at: "2026-10-11T08:00:00" },
        { id: "h2", message: "Q2", response: "A2", model: "m", created_at: "2026-10-11T08:01:00" },
      ],
    });

    expect(state.load).toEqual({ status: "idle" });
    expect(state.messages.map((message) => message.content)).toEqual(["Q1", "A1", "Q2", "A2"]);

    state = chatReducer(state, {
      type: "submit",
      conversationId: "c2",
      userId: "u2",
      assistantId: "a2",
      prompt: "Q3",
      mode: "agent",
      now: 1,
    });
    expect(state.conversationId).toBe("c2");
    expect(state.messages).toHaveLength(6);
  });

  it("ignores a load result for a conversation that is no longer open", () => {
    let state = chatReducer(initialChatState, { type: "loadStarted", conversationId: "c2" });
    state = chatReducer(state, { type: "loadStarted", conversationId: "c3" });
    state = chatReducer(state, { type: "loadFailed", conversationId: "c2", notFound: true, error: "" });

    expect(state).toMatchObject({ conversationId: "c3", load: { status: "loading" } });

    state = chatReducer(state, { type: "loadFailed", conversationId: "c3", notFound: true, error: "" });
    expect(state.load).toEqual({ status: "not_found" });
  });

  it("starts over on reset", () => {
    expect(chatReducer(submitted(), { type: "reset" })).toEqual(initialChatState);
  });
});
