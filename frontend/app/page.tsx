"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";

export default function Home() {
  const router = useRouter();
  const { user, token } = useAuthStore();

  useEffect(() => {
    if (token && user) {
      if (user.role === "physician") {
        router.replace("/physician/dashboard");
      } else {
        router.replace("/patient/home");
      }
    } else {
      router.replace("/login");
    }
  }, [token, user, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-crosscure-50 to-teal-50">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 rounded-2xl gradient-bg flex items-center justify-center">
          <span className="text-white text-xl font-bold">C</span>
        </div>
        <div className="w-6 h-6 border-3 border-crosscure-600 border-t-transparent rounded-full animate-spin" />
      </div>
    </div>
  );
}
