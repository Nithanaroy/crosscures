"use client";
import { useEffect } from "react";
import { useAuthStore } from "@/lib/store";

export default function StoreHydration() {
  useEffect(() => {
    useAuthStore.persist.rehydrate();
  }, []);

  return null;
}
