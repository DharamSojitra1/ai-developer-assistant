import { ChevronDown } from "lucide-react";
import { forwardRef, useId, type SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

import { fieldClass } from "./TextField";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: { value: string; label: string }[];
  hint?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, options, hint, id, className, ...props },
  ref,
) {
  const generatedId = useId();
  const selectId = id ?? generatedId;

  return (
    <div className="space-y-1.5">
      <label htmlFor={selectId} className="block text-[0.8125rem] font-medium text-fg">
        {label}
      </label>
      <div className="relative">
        <select
          ref={ref}
          id={selectId}
          aria-describedby={hint ? `${selectId}-hint` : undefined}
          className={cn(fieldClass, "h-10 appearance-none pr-9", className)}
          {...props}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-subtle" aria-hidden />
      </div>
      {hint && (
        <p id={`${selectId}-hint`} className="text-xs text-subtle">
          {hint}
        </p>
      )}
    </div>
  );
});
