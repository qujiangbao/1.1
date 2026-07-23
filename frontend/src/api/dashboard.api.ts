import client from "./client";

export const dashboardApi = {
  getOverview: async () => {
    const { data } = await client.get("/dashboard/overview");
    return data;
  },
};
