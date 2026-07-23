import client from "./client";

export const agentApi = {
  chat: async (message: string, conversationId?: string) => {
    const { data } = await client.post("/agent/chat", {
      message,
      conversation_id: conversationId,
      stream: false,
    });
    return data;
  },

  getTask: async (taskId: string) => {
    const { data } = await client.get(`/agent/task/${taskId}`);
    return data;
  },

  getTrace: async (taskId: string) => {
    const { data } = await client.get(`/agent/task/${taskId}/trace`);
    return data;
  },

  getStatus: async () => {
    const { data } = await client.get("/agent/status");
    return data;
  },
};
