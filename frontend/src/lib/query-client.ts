import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2, // 2 minutes
      retry: (count, err) => count < 1 && !/^(401|403|404)/.test(String(err)),
      refetchOnWindowFocus: false,
    },
  },
});
