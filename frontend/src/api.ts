import { useQuery } from "@tanstack/react-query";
export async function api<T>(
  path: string,
  data?: unknown,
  method = "POST",
): Promise<T> {
  const csrf =
    document.cookie
      .split("; ")
      .find((x) => x.startsWith("csrftoken="))
      ?.split("=")[1] ?? "";
  const res = await fetch("/api/v1/" + path, {
    credentials: "same-origin",
    ...(data !== undefined
      ? {
          method,
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": decodeURIComponent(csrf),
          },
          body: JSON.stringify(data),
        }
      : {}),
  });
  if (!res.ok) {
    let detail;
    try {
      detail = await res.json();
    } catch {
      detail = { detail: "Service unavailable" };
    }
    throw new Error(
      typeof detail.detail === "string"
        ? detail.detail
        : JSON.stringify(detail),
    );
  }
  return res.json();
}
export function useResource<T>(path: string, interval?: number) {
  return useQuery({
    queryKey: [path],
    queryFn: () => api<T>(path),
    refetchInterval: interval,
    staleTime: interval ? 0 : 60000,
    retry: 1,
  });
}
