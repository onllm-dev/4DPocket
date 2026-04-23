import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, isLoggedIn } from "@/api/client";

interface User {
  id: string;
  username: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  role: string;
  is_active: boolean;
  bio: string | null;
  created_at: string;
}

export function useCurrentUser() {
  return useQuery<User>({
    queryKey: ["currentUser"],
    queryFn: () => api.get("/api/v1/auth/me"),
    enabled: isLoggedIn(),
    retry: (failureCount, err) => failureCount < 1 && !(err instanceof Error && err.message.startsWith("401")),
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: { identifier: string; password: string }) => {
      await api.login(data.identifier, data.password);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["currentUser"] });
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (data: { username: string; email: string; password: string; display_name?: string }) =>
      api.register(data.email, data.password, data.display_name, data.username),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.logout(),
    onSuccess: () => {
      qc.clear();
      window.location.href = "/login";
    },
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      display_name?: string;
      bio?: string;
      avatar_url?: string;
      username?: string;
      email?: string;
    }) => api.patch("/api/v1/auth/me", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["currentUser"] }),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { current_password: string; new_password: string }) =>
      api.patch("/api/v1/auth/password", data),
  });
}

export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { current_password: string }) =>
      api.del("/api/v1/auth/me", data),
    onSuccess: () => {
      qc.clear();
      window.location.href = "/login";
    },
  });
}
