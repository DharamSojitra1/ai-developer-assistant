import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  icon: ReactNode;
  size?: "sm" | "md";
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, size = "md", className, type = "button", title, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={title ?? label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-control text-muted transition-colors",
        "hover:bg-hover hover:text-fg disabled:pointer-events-none disabled:opacity-40",
        size === "sm" ? "size-7 [&_svg]:size-3.5" : "size-9 [&_svg]:size-[1.125rem]",
        className,
      )}
      {...props}
    >
      {icon}
    </button>
  );
});
