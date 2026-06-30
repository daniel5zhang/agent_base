"use client";

import {
  RuntimeAdapterProvider,
  useAui,
  type GenericThreadHistoryAdapter,
  type MessageFormatAdapter,
  type MessageFormatItem,
  type MessageFormatRepository,
  type RemoteThreadListAdapter,
  type ThreadHistoryAdapter,
} from "@assistant-ui/react";
import type { UIMessage } from "ai";
import { useMemo, type PropsWithChildren } from "react";

const TENANT_ID = "tenant_demo";
const WORKSPACE_ID = "workspace_default";
const USER_ID = "user_demo";

type ThreadsResponse = {
  threads: Array<{
    thread_id: string;
    title?: string;
    workspace_id: string;
    status?: "regular" | "archived";
    last_message?: string;
    last_message_at?: string | null;
    message_count?: number;
  }>;
};

type ThreadDetailResponse = {
  thread: {
    thread_id: string;
    title?: string;
    workspace_id: string;
    status?: "regular" | "archived";
    created_at?: string | null;
  };
  messages: Array<{
    message_id: string;
    role: "user" | "assistant" | "system" | string;
    content: string;
    run_id?: string | null;
    created_at?: string | null;
  }>;
};

function threadQuery() {
  return `tenant_id=${encodeURIComponent(TENANT_ID)}&workspace_id=${encodeURIComponent(WORKSPACE_ID)}&user_id=${encodeURIComponent(USER_ID)}`;
}

function isUiMessageRole(role: string): role is UIMessage["role"] {
  return role === "user" || role === "assistant" || role === "system";
}

function serverMessageToUiMessage(message: ThreadDetailResponse["messages"][number]): UIMessage | undefined {
  if (!isUiMessageRole(message.role)) return undefined;
  return {
    id: message.message_id,
    role: message.role,
    metadata: {
      ...(message.run_id ? { run_id: message.run_id } : undefined),
      ...(message.created_at ? { created_at: message.created_at } : undefined),
    },
    parts: [{ type: "text", text: message.content }],
  };
}

async function fetchThreadDetail(threadId: string): Promise<ThreadDetailResponse | undefined> {
  const response = await fetch(`/api/threads/${encodeURIComponent(threadId)}?${threadQuery()}`);
  if (response.status === 404) return undefined;
  if (!response.ok) throw new Error(`thread_detail_http_${response.status}`);
  return response.json() as Promise<ThreadDetailResponse>;
}

async function patchThread(threadId: string, body: Record<string, unknown>) {
  const response = await fetch(`/api/threads/${encodeURIComponent(threadId)}?${threadQuery()}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`thread_update_http_${response.status}`);
}

async function deleteThread(threadId: string) {
  const response = await fetch(`/api/threads/${encodeURIComponent(threadId)}?${threadQuery()}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error(`thread_delete_http_${response.status}`);
}

class WorkbenchThreadHistoryAdapter implements ThreadHistoryAdapter {
  constructor(private readonly getThreadId: () => string | undefined) {}

  async load() {
    return { headId: null, messages: [] };
  }

  private async loadUiMessages() {
    const threadId = this.getThreadId();
    if (!threadId) return { headId: null, messages: [] };
    const detail = await fetchThreadDetail(threadId);
    if (!detail) return { headId: null, messages: [] };

    const messages = detail.messages
      .map(serverMessageToUiMessage)
      .filter((message): message is UIMessage => Boolean(message))
      .map((message, index, all) => ({
        parentId: index > 0 ? all[index - 1]?.id ?? null : null,
        message,
      }));

    return {
      headId: messages.at(-1)?.message.id ?? null,
      messages,
    };
  }

  async append() {
    // The Python agent runtime records messages when /api/chat invokes /api/agent/run.
    // Avoid duplicating rows from assistant-ui client-side persistence.
  }

  withFormat<TMessage, TStorageFormat extends Record<string, unknown>>(
    formatAdapter: MessageFormatAdapter<TMessage, TStorageFormat>,
  ): GenericThreadHistoryAdapter<TMessage> {
    const load = async (): Promise<MessageFormatRepository<TMessage>> => {
      const repo = await this.loadUiMessages();
      return {
        headId: repo.headId,
        messages: repo.messages
          .map((item): MessageFormatItem<TMessage> | undefined => {
            const message = item.message as unknown as TMessage;
            return {
              parentId: item.parentId,
              message,
            };
          })
          .filter((item): item is MessageFormatItem<TMessage> => {
            if (!item) return false;
            try {
              formatAdapter.getId(item.message);
              return true;
            } catch {
              return false;
            }
          }),
      };
    };

    return {
      load,
      append: async () => {},
      update: async () => {},
      delete: async () => {},
    };
  }
}

function WorkbenchRuntimeAdapterProvider({ children }: PropsWithChildren) {
  const aui = useAui();
  const history = useMemo(
    () =>
      new WorkbenchThreadHistoryAdapter(() =>
        aui.threadListItem.source ? aui.threadListItem().getState().remoteId : undefined,
      ),
    [aui],
  );

  return (
    <RuntimeAdapterProvider adapters={{ history }}>
      {children}
    </RuntimeAdapterProvider>
  );
}

export function createWorkbenchThreadListAdapter(): RemoteThreadListAdapter {
  return {
    async list() {
      const response = await fetch(`/api/threads?${threadQuery()}`);
      if (!response.ok) throw new Error(`thread_list_http_${response.status}`);
      const body = await response.json() as ThreadsResponse;
      return {
        threads: body.threads.map((thread) => ({
          status: thread.status ?? "regular",
          remoteId: thread.thread_id,
          externalId: undefined,
          title: thread.title || thread.last_message || "历史会话",
          lastMessageAt: thread.last_message_at
            ? new Date(thread.last_message_at)
            : undefined,
          custom: {
            workspace_id: thread.workspace_id,
            message_count: thread.message_count ?? 0,
            last_message: thread.last_message ?? "",
          },
        })),
      };
    },
    async initialize(threadId) {
      return { remoteId: threadId, externalId: undefined };
    },
    async fetch(threadId) {
      const detail = await fetchThreadDetail(threadId);
      if (!detail) {
        return {
          status: "regular" as const,
          remoteId: threadId,
          externalId: undefined,
          title: "新会话",
        };
      }
      return {
        status: detail.thread.status ?? "regular",
        remoteId: detail.thread.thread_id,
        externalId: undefined,
        title: detail.thread.title || "历史会话",
        lastMessageAt: detail.messages.at(-1)?.created_at
          ? new Date(detail.messages.at(-1)!.created_at!)
          : undefined,
        custom: { workspace_id: detail.thread.workspace_id },
      };
    },
    async rename(threadId, newTitle) {
      await patchThread(threadId, { title: newTitle });
    },
    async updateCustom(threadId, custom) {
      await patchThread(threadId, { custom });
    },
    async archive(threadId) {
      await patchThread(threadId, { status: "archived" });
    },
    async unarchive(threadId) {
      await patchThread(threadId, { status: "regular" });
    },
    async delete(threadId) {
      await deleteThread(threadId);
    },
    async generateTitle() {
      return new ReadableStream();
    },
    unstable_Provider: WorkbenchRuntimeAdapterProvider,
  };
}
