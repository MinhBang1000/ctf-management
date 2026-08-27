"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { MemberMe, SuperAdminMe } from "@/lib/types";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    (async () => {
      try {
        await api.get<MemberMe>("/api/v1/auth/me");
        router.replace("/dashboard");
        return;
      } catch (err) {
        if (!(err instanceof ApiError)) throw err;
      }
      try {
        await api.get<SuperAdminMe>("/admin/auth/me");
        router.replace("/console");
        return;
      } catch (err) {
        if (!(err instanceof ApiError)) throw err;
      }
      router.replace("/login");
    })();
  }, [router]);

  return null;
}
