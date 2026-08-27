"use client";

import { createContext, useContext } from "react";
import type { MemberMe } from "@/lib/types";

export const MemberContext = createContext<MemberMe | null>(null);

export function useMember(): MemberMe {
  const member = useContext(MemberContext);
  if (!member) throw new Error("useMember must be used within the dashboard layout");
  return member;
}
