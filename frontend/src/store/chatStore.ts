import { create } from "zustand";
import { agentApi } from "@/api/agent.api";
import type { ChatResponse } from "@/types/agent";

interface Message {
  role: "user" | "assistant";
  content: string;
  agents?: string[];
}

interface ChatStore {
  messages: Message[];
  isStreaming: boolean;
  sendMessage: (text: string) => Promise<ChatResponse>;
  clearMessages: () => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  isStreaming: false,

  sendMessage: async (text: string) => {
    set({ isStreaming: true });

    const userMsg: Message = { role: "user", content: text };
    set((s) => ({ messages: [...s.messages, userMsg] }));

    try {
      const res = await agentApi.chat(text);
      const aiMsg: Message = {
        role: "assistant",
        content: res.response || "完成",
        agents: res.agents_used,
      };
      set((s) => ({ messages: [...s.messages, aiMsg], isStreaming: false }));
      return res;
    } catch {
      set((s) => ({
        messages: [...s.messages, { role: "assistant", content: "处理出错了" }],
        isStreaming: false,
      }));
      throw new Error("Chat failed");
    }
  },

  clearMessages: () => set({ messages: [] }),
}));
