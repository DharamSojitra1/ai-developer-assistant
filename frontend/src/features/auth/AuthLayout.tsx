import type { ReactNode } from "react";

import { Logo } from "@/components/layout/Logo";

export function AuthLayout({ title, subtitle, children, footer }: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <main className="flex min-h-full flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-[22rem]">
        <Logo className="mb-10" />
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1.5 text-sm text-muted">{subtitle}</p>
        <div className="mt-8">{children}</div>
        <p className="mt-8 text-sm text-muted">{footer}</p>
      </div>
    </main>
  );
}
